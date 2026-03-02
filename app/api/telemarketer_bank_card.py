"""
电销人员银行卡接口 - 查询/绑定自己的银行卡
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.mysql import get_db
from app.models.bank_card import BankCard
from app.core.permission import require_permission
from app.core.response import success_response, error_response, ErrorCode

router = APIRouter()


@router.get("/admin/telemarketer/bank-card", summary="电销人员-查询我的银行卡")
@require_permission("telemarketer:view")
async def get_my_bank_card(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        admin_id = request.state.admin["admin_id"]
        result = await db.execute(select(BankCard).where(BankCard.admin_id == admin_id))
        card = result.scalar_one_or_none()

        if not card:
            return success_response(data=None)

        return success_response(data={
            "id": card.id,
            "card_holder_name": card.card_holder_name,
            "card_number": card.card_number,
            "bank_name": card.bank_name,
            "created_at": card.created_at.strftime("%Y-%m-%d %H:%M:%S") if card.created_at else None,
            "updated_at": card.updated_at.strftime("%Y-%m-%d %H:%M:%S") if card.updated_at else None,
        })
    except Exception as e:
        logger.error(f"查询银行卡失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="查询失败")


class BindBankCardRequest(BaseModel):
    card_holder_name: str
    card_number: str
    bank_name: str


@router.post("/admin/telemarketer/bank-card", summary="电销人员-绑定/更新银行卡")
@require_permission("telemarketer:view")
async def bind_bank_card(
    request: Request,
    body: BindBankCardRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        if not body.card_holder_name.strip():
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="持卡人姓名不能为空")
        if not body.card_number.strip():
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="银行卡号不能为空")
        if not body.bank_name.strip():
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="银行名称不能为空")

        admin_id = request.state.admin["admin_id"]
        result = await db.execute(select(BankCard).where(BankCard.admin_id == admin_id))
        existing = result.scalar_one_or_none()

        if existing:
            existing.card_holder_name = body.card_holder_name.strip()
            existing.card_number = body.card_number.strip()
            existing.bank_name = body.bank_name.strip()
        else:
            db.add(BankCard(
                admin_id=admin_id,
                card_holder_name=body.card_holder_name.strip(),
                card_number=body.card_number.strip(),
                bank_name=body.bank_name.strip(),
            ))

        await db.commit()
        return success_response(message="绑定成功")
    except Exception as e:
        logger.error(f"绑定银行卡失败: {e}")
        await db.rollback()
        return error_response(code=ErrorCode.DATABASE_ERROR, message="绑定失败")
