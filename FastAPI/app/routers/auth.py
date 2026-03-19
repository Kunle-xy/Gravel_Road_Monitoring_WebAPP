from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models import User, RefreshToken
from app.schemas import UserCreate, UserLogin, UserResponse, Token, EmailOnly
from app.auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_active_user, create_refresh_token,
    validate_refresh_token, revoke_user_refresh_tokens,
)
from app.config import settings
from app.email import send_verification_email, create_verification_token
from jose import JWTError, jwt

router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.CELERY_BROKER_URL,
)

def _is_prod() -> bool:
    return settings.FRONTEND_URL.startswith("https://")

def _set_auth_cookies(response: JSONResponse, access_token: str, refresh_token: str):
    is_prod = _is_prod()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="strict" if is_prod else "lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="strict" if is_prod else "lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )

def _clear_auth_cookies(response: JSONResponse):
    is_prod = _is_prod()
    for key in ["access_token", "refresh_token"]:
        response.delete_cookie(
            key=key,
            path="/",
            secure=is_prod,
            samesite="strict" if is_prod else "lax",
        )

@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if not existing_user:
        hashed_password = get_password_hash(user_data.password)
        new_user = User(
            email=user_data.email,
            password_hash=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            organization=user_data.organization,
            is_active=False,
            email_verified=False,
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        try:
            send_verification_email(new_user.email, new_user.first_name)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to send verification email to {new_user.email}: {e}")

    # Same response whether email exists or not — prevents enumeration
    return {"message": "If this email is available, a verification link has been sent. Check your inbox."}

@router.post("/login")
@limiter.limit("20/minute")
def login(request: Request, user_credentials: UserLogin, db: Session = Depends(get_db)):
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

    user = db.query(User).filter(User.email == user_credentials.email).first()

    # Check account lockout
    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account temporarily locked due to too many failed attempts. Try again in {remaining} minutes."
        )

    if not user or not verify_password(user_credentials.password, user.password_hash):
        # Increment failed attempts if user exists
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in. Check your inbox for a verification link."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account has been deactivated. Contact support for assistance."
        )

    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_tok = create_refresh_token(user.id, db)

    response = JSONResponse(content={"message": "Login successful"})
    _set_auth_cookies(response, access_token, refresh_tok)
    return response

@router.post("/refresh")
@limiter.limit("30/minute")
def refresh(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    db_token = validate_refresh_token(token, db)
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user or not user.is_active:
        db_token.revoked = True
        db.commit()
        resp = JSONResponse(status_code=401, content={"detail": "User not found or inactive"})
        _clear_auth_cookies(resp)
        return resp

    # Rotate: revoke old, issue new pair
    db_token.revoked = True
    db.commit()

    new_access = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    new_refresh = create_refresh_token(user.id, db, family_id=db_token.family_id)

    response = JSONResponse(content={"message": "Tokens refreshed"})
    _set_auth_cookies(response, new_access, new_refresh)
    return response

@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    # Revoke the refresh token if present
    token = request.cookies.get("refresh_token")
    if token:
        db_token = db.query(RefreshToken).filter_by(token=token, revoked=False).first()
        if db_token:
            db_token.revoked = True
            db.commit()

    response = JSONResponse(content={"message": "Logged out"})
    _clear_auth_cookies(response)
    return response

@router.get("/verify")
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != "email_verify":
            raise HTTPException(status_code=400, detail="Invalid verification link")
        email = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    user = db.query(User).filter(User.email == email).first()
    if not user or user.email_verified:
        # Generic response prevents user enumeration
        return {"message": "Email verified. You can now log in."}

    user.email_verified = True
    user.is_active = True
    db.commit()

    return {"message": "Email verified. You can now log in."}

@router.post("/resend-verification")
@limiter.limit("10/hour")
def resend_verification(request: Request, user_data: EmailOnly, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or user.email_verified:
        # Generic response to prevent enumeration
        return {"message": "If an unverified account exists, a new verification email has been sent."}

    try:
        send_verification_email(user.email, user.first_name)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to send verification email. Try again later.")

    return {"message": "If an unverified account exists, a new verification email has been sent."}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user