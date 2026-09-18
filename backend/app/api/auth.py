"""Auth API: register / login / me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.db.session import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_policy(cls, v: str) -> str:
        error = validate_password_strength(v)
        if error:
            raise ValueError(error)
        return v


class LoginRequest(BaseModel):
    account: str  # email or username
    password: str
    remember: bool = False


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    email = payload.email.strip().lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="用户名已被占用")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="邮箱已被注册")
    user = User(username=username, email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return {
        "token": token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    account = payload.account.strip().lower()
    user = db.query(User).filter((User.email == account) | (User.username == payload.account.strip())).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码不正确")
    token = create_access_token(user.id, remember=payload.remember)
    return {
        "token": token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }
