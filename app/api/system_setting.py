"""
系统参数设置接口
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.mysql import get_db
from app.models.system_setting import SystemSetting
from app.core.permission import require_permission
from app.core.auth import get_client_ip
from app.core.response import success_response, error_response, ErrorCode
from app.utils.log_helper import record_operation

router = APIRouter()


@router.get("/admin/settings", summary="获取所有参数设置")
@require_permission("setting:view")
async def get_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(SystemSetting).order_by(SystemSetting.id))
        rows = result.scalars().all()
        data = {r.setting_key: {
            "value": r.setting_value,
            "description": r.description,
        } for r in rows}
        return success_response(data=data)
    except Exception as e:
        logger.error(f"获取参数设置失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="获取失败")


class UpdateSettingRequest(BaseModel):
    setting_key: str
    setting_value: str


@router.post("/admin/settings", summary="更新参数设置")
@require_permission("setting:edit")
async def update_setting(
    request: Request,
    body: UpdateSettingRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(SystemSetting).where(SystemSetting.setting_key == body.setting_key))
        setting = result.scalar_one_or_none()
        if not setting:
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="参数不存在")

        old_value = setting.setting_value
        setting.setting_value = body.setting_value

        admin = request.state.admin
        await record_operation(db, admin["admin_id"], admin["username"], "setting", "修改参数设置",
                               detail={"key": body.setting_key, "old": old_value, "new": body.setting_value},
                               ip=get_client_ip(request))
        await db.commit()
        return success_response(message="保存成功")
    except Exception as e:
        logger.error(f"更新参数设置失败: {e}")
        await db.rollback()
        return error_response(code=ErrorCode.DATABASE_ERROR, message="保存失败")
