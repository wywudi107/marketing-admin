"""
管理员管理 & 角色管理接口
"""
from fastapi import APIRouter, Depends, Request, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.mysql import get_db
from app.database.redis import redis_db
from app.models.admin_user import AdminUser
from app.models.admin_role import AdminRole
from app.core.permission import require_permission
from app.core.auth import hash_password, get_client_ip
from app.core.response import success_response, error_response, ErrorCode
from app.utils.pagination import get_pagination, pagination_response
from app.utils.log_helper import record_operation

router = APIRouter()


# ==================== 管理员管理 ====================

@router.get("/admin/admins", summary="管理员列表")
@require_permission("admin_user:view")
async def get_admins(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    try:
        total = (await db.execute(select(func.count()).select_from(AdminUser))).scalar() or 0
        p = get_pagination(page, page_size)
        result = await db.execute(
            select(AdminUser, AdminRole.role_name)
            .outerjoin(AdminRole, AdminUser.role_id == AdminRole.id)
            .order_by(AdminUser.id.asc())
            .offset(p["offset"]).limit(p["page_size"])
        )
        rows = result.all()

        admin_list = [{
            "id": row.AdminUser.id,
            "username": row.AdminUser.username,
            "nickname": row.AdminUser.nickname,
            "role_id": row.AdminUser.role_id,
            "role_name": row.role_name,
            "status": row.AdminUser.status,
            "last_login_at": row.AdminUser.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if row.AdminUser.last_login_at else None,
            "last_login_ip": row.AdminUser.last_login_ip,
            "created_at": row.AdminUser.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.AdminUser.created_at else None,
        } for row in rows]

        return success_response(data=pagination_response(admin_list, total, p["page"], p["page_size"]))
    except Exception as e:
        logger.error(f"获取管理员列表失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="获取列表失败")


class AdminCreateRequest(BaseModel):
    username: str
    password: str
    nickname: Optional[str] = None
    role_id: int


@router.post("/admin/admins", summary="创建管理员")
@require_permission("admin_user:create")
async def create_admin(request: Request, body: AdminCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        # 检查用户名是否已存在
        exists = await db.execute(select(AdminUser).where(AdminUser.username == body.username))
        if exists.scalar_one_or_none():
            return error_response(code=ErrorCode.DUPLICATE_RECORD, message="用户名已存在")

        # 检查角色是否存在
        role = await db.execute(select(AdminRole).where(AdminRole.id == body.role_id))
        if not role.scalar_one_or_none():
            return error_response(code=ErrorCode.RECORD_NOT_FOUND, message="角色不存在")

        admin_user = AdminUser(
            username=body.username,
            password=hash_password(body.password),
            nickname=body.nickname,
            role_id=body.role_id,
        )
        db.add(admin_user)

        admin = request.state.admin
        await record_operation(db, admin["admin_id"], admin["username"], "system", "创建管理员",
                               detail={"new_admin": body.username, "role_id": body.role_id},
                               ip=get_client_ip(request))
        await db.commit()
        return success_response(data={"id": admin_user.id}, message="创建成功")
    except Exception as e:
        logger.error(f"创建管理员失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="创建失败")


class AdminUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    role_id: Optional[int] = None
    status: Optional[int] = None
    password: Optional[str] = None


@router.put("/admin/admins/{admin_id}", summary="编辑管理员")
@require_permission("admin_user:edit")
async def update_admin(request: Request, admin_id: int, body: AdminUpdateRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
        admin_user = result.scalar_one_or_none()
        if not admin_user:
            return error_response(code=ErrorCode.RECORD_NOT_FOUND, message="管理员不存在")

        if body.nickname is not None:
            admin_user.nickname = body.nickname
        if body.role_id is not None:
            admin_user.role_id = body.role_id
        if body.status is not None:
            admin_user.status = body.status
        if body.password:
            admin_user.password = hash_password(body.password)

        admin = request.state.admin
        await record_operation(db, admin["admin_id"], admin["username"], "system", "编辑管理员",
                               target_id=str(admin_id), ip=get_client_ip(request))
        await db.commit()
        return success_response(message="修改成功")
    except Exception as e:
        logger.error(f"编辑管理员失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="操作失败")


@router.delete("/admin/admins/{admin_id}", summary="删除管理员")
@require_permission("admin_user:delete")
async def delete_admin(request: Request, admin_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
        admin_user = result.scalar_one_or_none()
        if not admin_user:
            return error_response(code=ErrorCode.RECORD_NOT_FOUND, message="管理员不存在")

        admin = request.state.admin
        if admin["admin_id"] == admin_id:
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="不能删除自己")

        await record_operation(db, admin["admin_id"], admin["username"], "system", "删除管理员",
                               target_id=str(admin_id), detail={"deleted_admin": admin_user.username},
                               ip=get_client_ip(request))

        # 清除被删除管理员的 token
        await redis_db.delete_admin_token(admin_id)

        await db.delete(admin_user)
        await db.commit()
        return success_response(message="删除成功")
    except Exception as e:
        logger.error(f"删除管理员失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="操作失败")


# ==================== 角色管理 ====================

@router.get("/admin/roles", summary="角色列表")
@require_permission("admin_role:view")
async def get_roles(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(AdminRole).order_by(AdminRole.id.asc()))
        roles = result.scalars().all()

        role_list = [{
            "id": r.id,
            "role_name": r.role_name,
            "role_key": r.role_key,
            "permissions": r.permissions or [],
            "status": r.status,
            "remark": r.remark,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
        } for r in roles]

        return success_response(data=role_list)
    except Exception as e:
        logger.error(f"获取角色列表失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="获取列表失败")


class RoleCreateRequest(BaseModel):
    role_name: str
    role_key: str
    permissions: List[str]
    status: int = 1
    remark: Optional[str] = None


@router.post("/admin/roles", summary="创建角色")
@require_permission("admin_role:create")
async def create_role(request: Request, body: RoleCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        exists = await db.execute(select(AdminRole).where(AdminRole.role_key == body.role_key))
        if exists.scalar_one_or_none():
            return error_response(code=ErrorCode.DUPLICATE_RECORD, message="角色标识已存在")

        role = AdminRole(
            role_name=body.role_name,
            role_key=body.role_key,
            permissions=body.permissions,
            status=body.status,
            remark=body.remark,
        )
        db.add(role)

        admin = request.state.admin
        await record_operation(db, admin["admin_id"], admin["username"], "system", "创建角色",
                               detail={"role_key": body.role_key}, ip=get_client_ip(request))
        await db.commit()
        return success_response(data={"id": role.id}, message="创建成功")
    except Exception as e:
        logger.error(f"创建角色失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="创建失败")


class RoleUpdateRequest(BaseModel):
    role_name: Optional[str] = None
    permissions: Optional[List[str]] = None
    status: Optional[int] = None
    remark: Optional[str] = None


@router.put("/admin/roles/{role_id}", summary="编辑角色")
@require_permission("admin_role:edit")
async def update_role(request: Request, role_id: int, body: RoleUpdateRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(AdminRole).where(AdminRole.id == role_id))
        role = result.scalar_one_or_none()
        if not role:
            return error_response(code=ErrorCode.RECORD_NOT_FOUND, message="角色不存在")

        if body.role_name is not None:
            role.role_name = body.role_name
        if body.permissions is not None:
            role.permissions = body.permissions
        if body.status is not None:
            role.status = body.status
        if body.remark is not None:
            role.remark = body.remark

        admin = request.state.admin
        await record_operation(db, admin["admin_id"], admin["username"], "system", "编辑角色",
                               target_id=str(role_id), ip=get_client_ip(request))
        await db.commit()
        return success_response(message="修改成功")
    except Exception as e:
        logger.error(f"编辑角色失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="操作失败")


@router.delete("/admin/roles/{role_id}", summary="删除角色")
@require_permission("admin_role:delete")
async def delete_role(request: Request, role_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(AdminRole).where(AdminRole.id == role_id))
        role = result.scalar_one_or_none()
        if not role:
            return error_response(code=ErrorCode.RECORD_NOT_FOUND, message="角色不存在")

        # 检查是否有管理员使用此角色
        admin_count = await db.execute(
            select(func.count()).select_from(AdminUser).where(AdminUser.role_id == role_id)
        )
        if (admin_count.scalar() or 0) > 0:
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="该角色下还有管理员，不可删除")

        admin = request.state.admin
        await record_operation(db, admin["admin_id"], admin["username"], "system", "删除角色",
                               target_id=str(role_id), detail={"role_key": role.role_key},
                               ip=get_client_ip(request))
        await db.delete(role)
        await db.commit()
        return success_response(message="删除成功")
    except Exception as e:
        logger.error(f"删除角色失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="操作失败")
