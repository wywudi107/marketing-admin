"""
结算申请接口 - 电销人员申请 + 管理员审核
"""
from fastapi import APIRouter, Depends, Request, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.mysql import get_db
from app.models.settlement import SettlementApplication
from app.models.bank_card import BankCard
from app.models.daily_stats import DailyStats
from app.models.system_setting import SystemSetting
from app.core.permission import require_permission
from app.core.auth import get_client_ip
from app.core.response import success_response, error_response, ErrorCode
from app.utils.pagination import get_pagination, pagination_response
from app.utils.log_helper import record_operation

router = APIRouter()


# ========== 电销人员接口 ==========

class ApplyRequest(BaseModel):
    stat_date: str


@router.post("/admin/telemarketer/settlement/apply", summary="电销人员-申请结算")
@require_permission("telemarketer:view")
async def apply_settlement(
    request: Request,
    body: ApplyRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        admin_id = request.state.admin["admin_id"]
        username = request.state.admin["username"]

        # 检查银行卡
        card_result = await db.execute(select(BankCard).where(BankCard.admin_id == admin_id))
        card = card_result.scalar_one_or_none()
        if not card:
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="请先绑定银行卡")

        # 检查是否重复申请
        exist_result = await db.execute(
            select(SettlementApplication).where(
                SettlementApplication.admin_id == admin_id,
                SettlementApplication.stat_date == body.stat_date,
            )
        )
        if exist_result.scalar_one_or_none():
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="该日期已提交过结算申请")

        # 查询当日统计
        stat_result = await db.execute(
            select(DailyStats).where(DailyStats.invite_code == username, DailyStats.stat_date == body.stat_date)
        )
        stat = stat_result.scalar_one_or_none()
        first_recharge_count = stat.first_recharge_count if stat else 0

        if first_recharge_count == 0:
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="该日期没有首充数据，无法申请结算")

        # 查询提成参数
        setting_result = await db.execute(
            select(SystemSetting).where(SystemSetting.setting_key == 'telemarketer_commission')
        )
        setting = setting_result.scalar_one_or_none()
        commission = int(setting.setting_value) if setting else 0

        db.add(SettlementApplication(
            admin_id=admin_id,
            username=username,
            stat_date=body.stat_date,
            first_recharge_count=first_recharge_count,
            commission_per_person=commission,
            total_commission=commission * first_recharge_count,
            bank_name=card.bank_name,
            card_holder_name=card.card_holder_name,
            card_number=card.card_number,
        ))
        await db.commit()
        return success_response(message="申请已提交，等待审核")
    except Exception as e:
        logger.error(f"申请结算失败: {e}")
        await db.rollback()
        return error_response(code=ErrorCode.DATABASE_ERROR, message="申请失败")


@router.get("/admin/telemarketer/settlements", summary="电销人员-我的结算申请")
@require_permission("telemarketer:view")
async def get_my_settlements(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        admin_id = request.state.admin["admin_id"]

        count_stmt = select(func.count()).select_from(SettlementApplication).where(SettlementApplication.admin_id == admin_id)
        query_stmt = select(SettlementApplication).where(SettlementApplication.admin_id == admin_id).order_by(SettlementApplication.created_at.desc())

        total = (await db.execute(count_stmt)).scalar() or 0
        p = get_pagination(page, page_size)
        result = await db.execute(query_stmt.offset(p["offset"]).limit(p["page_size"]))
        rows = result.scalars().all()

        data_list = [_to_dict(r) for r in rows]
        return success_response(data=pagination_response(data_list, total, p["page"], p["page_size"]))
    except Exception as e:
        logger.error(f"查询我的结算申请失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="查询失败")


# ========== 管理员接口 ==========

@router.get("/admin/settlements", summary="管理员-结算申请列表")
@require_permission("marketing:view")
async def get_settlements(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[int] = Query(None, description="状态: 0待审核 1已通过 2已拒绝"),
    username: Optional[str] = Query(None, description="申请人用户名"),
    db: AsyncSession = Depends(get_db),
):
    try:
        count_stmt = select(func.count()).select_from(SettlementApplication)
        query_stmt = select(SettlementApplication).order_by(SettlementApplication.created_at.desc())

        if status is not None:
            count_stmt = count_stmt.where(SettlementApplication.status == status)
            query_stmt = query_stmt.where(SettlementApplication.status == status)
        if username:
            count_stmt = count_stmt.where(SettlementApplication.username == username)
            query_stmt = query_stmt.where(SettlementApplication.username == username)

        total = (await db.execute(count_stmt)).scalar() or 0
        p = get_pagination(page, page_size)
        result = await db.execute(query_stmt.offset(p["offset"]).limit(p["page_size"]))
        rows = result.scalars().all()

        data_list = [_to_dict(r) for r in rows]
        return success_response(data=pagination_response(data_list, total, p["page"], p["page_size"]))
    except Exception as e:
        logger.error(f"查询结算申请列表失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="查询失败")


class ReviewRequest(BaseModel):
    status: int  # 1通过 2拒绝
    remark: Optional[str] = None


@router.post("/admin/settlements/{app_id}/review", summary="管理员-审核结算申请")
@require_permission("marketing:view")
async def review_settlement(
    request: Request,
    app_id: int,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        if body.status not in (1, 2):
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="状态值无效")

        result = await db.execute(select(SettlementApplication).where(SettlementApplication.id == app_id))
        app = result.scalar_one_or_none()
        if not app:
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="申请记录不存在")
        if app.status != 0:
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="该申请已审核")

        app.status = body.status
        app.remark = body.remark

        admin = request.state.admin
        action = "通过" if body.status == 1 else "拒绝"
        await record_operation(db, admin["admin_id"], admin["username"], "settlement", f"审核结算申请-{action}",
                               detail={"app_id": app_id, "username": app.username, "amount": app.total_commission},
                               ip=get_client_ip(request))
        await db.commit()
        return success_response(message=f"已{action}")
    except Exception as e:
        logger.error(f"审核结算申请失败: {e}")
        await db.rollback()
        return error_response(code=ErrorCode.DATABASE_ERROR, message="操作失败")


def _to_dict(r):
    status_map = {0: '待审核', 1: '已通过', 2: '已拒绝'}
    return {
        "id": r.id,
        "username": r.username,
        "stat_date": r.stat_date,
        "first_recharge_count": r.first_recharge_count,
        "commission_per_person": r.commission_per_person,
        "total_commission": r.total_commission,
        "bank_name": r.bank_name,
        "card_holder_name": r.card_holder_name,
        "card_number": r.card_number,
        "status": r.status,
        "status_text": status_map.get(r.status, '未知'),
        "remark": r.remark,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
    }
