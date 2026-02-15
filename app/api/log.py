"""
操作日志查询接口
"""
from fastapi import APIRouter, Depends, Request, Query
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.mysql import get_db
from app.models.admin_log import AdminOperationLog
from app.core.permission import require_permission
from app.core.response import success_response, error_response, ErrorCode
from app.utils.pagination import get_pagination, pagination_response

router = APIRouter()


@router.get("/admin/operation-logs", summary="操作日志列表")
@require_permission("operation_log:view")
async def get_operation_logs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin_id: Optional[int] = None,
    module: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(AdminOperationLog)
        count_query = select(func.count()).select_from(AdminOperationLog)

        conditions = []
        if admin_id:
            conditions.append(AdminOperationLog.admin_id == admin_id)
        if module:
            conditions.append(AdminOperationLog.module == module)
        if action:
            conditions.append(AdminOperationLog.action.like(f"%{action}%"))
        if start_date:
            conditions.append(AdminOperationLog.created_at >= start_date)
        if end_date:
            conditions.append(AdminOperationLog.created_at <= end_date + " 23:59:59")

        for cond in conditions:
            query = query.where(cond)
            count_query = count_query.where(cond)

        total = (await db.execute(count_query)).scalar() or 0
        p = get_pagination(page, page_size)
        result = await db.execute(
            query.order_by(AdminOperationLog.id.desc()).offset(p["offset"]).limit(p["page_size"])
        )
        logs = result.scalars().all()

        log_list = [{
            "id": log.id,
            "admin_id": log.admin_id,
            "admin_username": log.admin_username,
            "module": log.module,
            "action": log.action,
            "target_id": log.target_id,
            "detail": log.detail,
            "ip": log.ip,
            "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else None,
        } for log in logs]

        return success_response(data=pagination_response(log_list, total, p["page"], p["page_size"]))
    except Exception as e:
        logger.error(f"获取操作日志失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="获取日志失败")
