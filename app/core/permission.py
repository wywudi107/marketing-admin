"""
RBAC 权限装饰器
"""
from functools import wraps
from fastapi import Request
from app.core.auth import get_current_admin
from app.core.response import error_response, ErrorCode


def require_permission(*permissions: str):
    """
    权限校验装饰器

    用法:
        @router.get("/admin/users")
        @require_permission("user:view")
        async def get_users(request: Request, ...):
            admin = request.state.admin
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get('request')
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if not request:
                return error_response(code=ErrorCode.UNAUTHORIZED, message="无法获取请求信息")

            admin = await get_current_admin(request)
            if not admin:
                return error_response(code=ErrorCode.UNAUTHORIZED, message="未登录或Token已过期")

            # super_admin 拥有所有权限
            admin_permissions = admin.get("permissions", [])
            role_key = admin.get("role_key", "")

            if role_key != "super_admin":
                for perm in permissions:
                    if perm not in admin_permissions:
                        return error_response(code=ErrorCode.PERMISSION_DENIED, message=f"无操作权限: {perm}")

            request.state.admin = admin
            return await func(*args, **kwargs)
        return wrapper
    return decorator
