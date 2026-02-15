"""
统一响应格式模块
"""
from typing import Any
from datetime import datetime


def success_response(data: Any = None, message: str = "success", code: int = 0) -> dict:
    return {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": int(datetime.now().timestamp())
    }


def error_response(code: int, message: str, data: Any = None) -> dict:
    return {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": int(datetime.now().timestamp())
    }


class ErrorCode:
    SUCCESS = 0
    UNKNOWN_ERROR = 10001
    INVALID_PARAMETER = 10002
    MISSING_PARAMETER = 10003
    RATE_LIMIT_EXCEEDED = 10005

    # 认证/授权
    UNAUTHORIZED = 20001
    TOKEN_EXPIRED = 20002
    TOKEN_INVALID = 20003
    PERMISSION_DENIED = 20004
    USER_NOT_FOUND = 20005
    USER_DISABLED = 20006
    INVALID_CREDENTIALS = 20008
    ACCOUNT_LOCKED = 20009
    INVALID_CAPTCHA = 20010

    # 业务
    INSUFFICIENT_BALANCE = 30007
    ORDER_NOT_FOUND = 40004
    ORDER_ALREADY_PROCESSED = 40005

    # 数据库
    DATABASE_ERROR = 60001
    RECORD_NOT_FOUND = 60002
    DUPLICATE_RECORD = 60003
