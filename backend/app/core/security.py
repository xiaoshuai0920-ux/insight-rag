"""Password hashing and JWT helpers."""
import re
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PASSWORD_POLICY_HINT = "至少 8 位，包含字母和数字"
_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


def validate_password_strength(password: str) -> str | None:
    """Return an error message when the password violates the policy."""
    if not password or not _PASSWORD_RE.match(password):
        return PASSWORD_POLICY_HINT
    return None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(user_id: int, remember: bool = False) -> str:
    minutes = (
        settings.JWT_REMEMBER_EXPIRE_MINUTES if remember else settings.JWT_EXPIRE_MINUTES
    )
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
