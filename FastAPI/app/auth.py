from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
import secrets
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import Optional

from app.config import settings
from app.database import get_db
from app.models import User, RefreshToken, ApprovedEmail, ApprovedDomain
from app.schemas import TokenData


def is_email_approved(db: Session, email: str) -> bool:
    """
    True if `email` is in the allowlist — either matched exactly in
    `approved_emails`, or whose domain is in `approved_domains`.
    """
    if not email:
        return False
    normalized = email.strip().lower()
    if db.query(ApprovedEmail).filter(ApprovedEmail.email == normalized).first():
        return True
    if "@" in normalized:
        domain = normalized.split("@", 1)[1]
        if db.query(ApprovedDomain).filter(ApprovedDomain.domain == domain).first():
            return True
    return False

# Use argon2 instead of bcrypt
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    # Set purpose if not already specified (default to "access")
    if "purpose" not in to_encode:
        to_encode["purpose"] = "access"
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(user_id, db: Session, family_id=None) -> str:
    import uuid as uuid_mod
    token = secrets.token_urlsafe(64)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_token = RefreshToken(
        user_id=user_id,
        token=token,
        family_id=family_id or uuid_mod.uuid4(),
        expires_at=expires_at,
    )
    db.add(db_token)
    db.commit()
    return token

def validate_refresh_token(token: str, db: Session) -> RefreshToken:
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == token,
    ).first()
    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    # Reuse detection: if token was already revoked, an attacker may have used it.
    # Revoke the entire token family to protect the user.
    if db_token.revoked:
        db.query(RefreshToken).filter(
            RefreshToken.family_id == db_token.family_id,
        ).update({"revoked": True})
        db.commit()
        raise HTTPException(status_code=401, detail="Token reuse detected. All sessions revoked for security.")
    if db_token.expires_at < datetime.now(timezone.utc):
        db_token.revoked = True
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")
    return db_token

def revoke_user_refresh_tokens(user_id, db: Session):
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False,
    ).update({"revoked": True})
    db.commit()

def get_token_from_cookie(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return token

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    token = get_token_from_cookie(request)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # Reject non-access tokens (e.g. email verification tokens)
        if payload.get("purpose") != "access":
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user