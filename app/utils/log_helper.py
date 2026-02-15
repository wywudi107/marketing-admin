"""
操作日志记录工具
"""
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admin_log import AdminOperationLog


async def record_operation(
    db: AsyncSession,
    admin_id: int,
    admin_username: str,
    module: str,
    action: str,
    target_id: str = None,
    detail: dict = None,
    ip: str = None
):
    log = AdminOperationLog(
        admin_id=admin_id,
        admin_username=admin_username,
        module=module,
        action=action,
        target_id=str(target_id) if target_id else None,
        detail=json.dumps(detail, ensure_ascii=False) if detail else None,
        ip=ip,
    )
    db.add(log)
