"""
电销人员每日统计接口 - 只能查看自己邀请码的数据（用户名即邀请码）
"""
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.mysql import get_db
from app.models.daily_stats import DailyStats
from app.models.system_setting import SystemSetting
from app.core.permission import require_permission
from app.core.response import success_response, error_response, ErrorCode
from app.utils.pagination import get_pagination, pagination_response

router = APIRouter()


@router.get("/admin/telemarketer-stats", summary="电销人员-每日统计")
@require_permission("telemarketer:view")
async def get_telemarketer_stats(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    try:
        # 用户名就是邀请码
        invite_code = request.state.admin["username"]

        count_stmt = select(func.count()).select_from(DailyStats).where(DailyStats.invite_code == invite_code)
        query_stmt = select(DailyStats).where(DailyStats.invite_code == invite_code).order_by(DailyStats.stat_date.desc())

        if start_date:
            count_stmt = count_stmt.where(DailyStats.stat_date >= start_date)
            query_stmt = query_stmt.where(DailyStats.stat_date >= start_date)
        if end_date:
            count_stmt = count_stmt.where(DailyStats.stat_date <= end_date)
            query_stmt = query_stmt.where(DailyStats.stat_date <= end_date)

        total = (await db.execute(count_stmt)).scalar() or 0
        p = get_pagination(page, page_size)
        result = await db.execute(query_stmt.offset(p["offset"]).limit(p["page_size"]))
        rows = result.scalars().all()

        data_list = [{
            "id": r.id,
            "stat_date": r.stat_date.strftime("%Y-%m-%d") if r.stat_date else None,
            "register_count": r.register_count,
            "first_recharge_count": r.first_recharge_count,
        } for r in rows]

        return success_response(data=pagination_response(data_list, total, p["page"], p["page_size"]))
    except Exception as e:
        logger.error(f"查询电销人员统计失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="查询失败")


@router.get("/admin/telemarketer/performance", summary="电销人员-查看提成业绩")
@require_permission("telemarketer:view")
async def get_telemarketer_performance(
    request: Request,
    stat_date: str = Query(..., description="统计日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    try:
        invite_code = request.state.admin["username"]

        # 查询当日统计
        result = await db.execute(
            select(DailyStats).where(DailyStats.invite_code == invite_code, DailyStats.stat_date == stat_date)
        )
        row = result.scalar_one_or_none()

        # 查询提成参数
        setting_result = await db.execute(
            select(SystemSetting).where(SystemSetting.setting_key == 'telemarketer_commission')
        )
        setting = setting_result.scalar_one_or_none()
        commission = int(setting.setting_value) if setting else 0

        first_recharge_count = row.first_recharge_count if row else 0
        total_commission = commission * first_recharge_count

        return success_response(data={
            "stat_date": stat_date,
            "first_recharge_count": first_recharge_count,
            "commission_per_person": commission,
            "total_commission": total_commission,
        })
    except Exception as e:
        logger.error(f"查询提成业绩失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="查询失败")
