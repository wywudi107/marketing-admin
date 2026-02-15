"""
JWT 认证模块
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Request
from loguru import logger

from app.config import config
from app.database.redis import redis_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    # bcrypt 限制密码最长 72 字节
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt 限制密码最长 72 字节
    return pwd_context.verify(plain_password[:72], hashed_password)


def create_access_token(data: dict, expires_hours: int = None) -> str:
    jwt_config = config.jwt
    expire_hours = expires_hours or jwt_config.get('expire_hours', 8)
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(hours=expire_hours)
    return jwt.encode(to_encode, jwt_config['secret_key'], algorithm=jwt_config.get('algorithm', 'HS256'))


def decode_token(token: str) -> Optional[dict]:
    try:
        jwt_config = config.jwt
        payload = jwt.decode(token, jwt_config['secret_key'], algorithms=[jwt_config.get('algorithm', 'HS256')])
        return payload
    except JWTError:
        return None


async def get_current_admin(request: Request) -> Optional[dict]:
    """从请求中提取并验证管理员身份"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    payload = decode_token(token)
    if not payload:
        return None

    admin_id = payload.get("admin_id")
    if not admin_id:
        return None

    # 验证 Redis 中的 token 是否一致（单点登录）
    stored_token = await redis_db.get_admin_token(admin_id)
    if stored_token != token:
        return None

    # 自动续期
    await redis_db.refresh_admin_token(admin_id)

    return payload


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
