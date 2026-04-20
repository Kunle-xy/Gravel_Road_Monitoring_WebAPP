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
    is_email_approved,
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
    if not is_email_approved(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This email is not authorized to register for this application. Please contact the administrator.",
        )
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if not existing_user:
        hashed_password = get_password_hash(user_data.password)
        new_user = User(
            email=user_data.email,
            password_hash=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            organization=user_data.organization,
            is_active=True,
            email_verified=True,
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    # Same response whether email exists or not — prevents enumeration
    return {"message": "Account created successfully. You can now log in."}

@router.post("/login")
@limiter.limit("20/minute")
def login(request: Request, user_credentials: UserLogin, db: Session = Depends(get_db)):
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

    if not is_email_approved(db, user_credentials.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not authorized. Please contact the administrator.",
        )

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


@router.post("/profile-picture")
def upload_profile_picture(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a presigned URL to upload a profile picture."""
    import boto3
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    s3_key = f"profile-pictures/{current_user.id}.jpg"

    presigned_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": s3_key,
            "ContentType": "image/jpeg",
        },
        ExpiresIn=300,
    )

    # Build the public CloudFront URL
    picture_url = f"https://{settings.AWS_CLOUDFRONT_DOMAIN}/{s3_key}"

    # Save to user record
    # Delete old S3 object if key changed
    if current_user.profile_picture_s3_key and current_user.profile_picture_s3_key != s3_key:
        try:
            s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=current_user.profile_picture_s3_key)
        except Exception:
            pass

    current_user.profile_picture_s3_key = s3_key
    current_user.profile_picture_url = picture_url
    db.commit()

    return {"presigned_url": presigned_url, "picture_url": picture_url}


@router.delete("/profile-picture", status_code=204)
def delete_profile_picture(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Remove the user's profile picture."""
    if current_user.profile_picture_s3_key:
        import boto3
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        try:
            s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=current_user.profile_picture_s3_key)
        except Exception:
            pass

    current_user.profile_picture_s3_key = None
    current_user.profile_picture_url = None
    db.commit()