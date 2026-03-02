"""
每日统计结果接口 - 分页查询、手动统计
"""
from fastapi import APIRouter, Depends, Request, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, func, case, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.mysql import get_db
from app.models.daily_stats import DailyStats
from app.models.first_recharge import FirstRecharge
from app.models.player_invite import PlayerInvite
from app.core.permission import require_permission
from app.core.auth import get_client_ip
from app.core.response import success_response, error_response, ErrorCode
from app.utils.pagination import get_pagination, pagination_response
from app.utils.log_helper import record_operation

router = APIRouter()


@router.get("/admin/daily-stats", summary="每日统计-分页查询")
@require_permission("marketing:view")
async def get_daily_stats(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
    invite_code: str = Query(None, description="邀请码"),
    avg_min: int = Query(None, description="首充RB值最小值"),
    avg_max: int = Query(None, description="首充RB值最大值"),
    db: AsyncSession = Depends(get_db),
):
    try:
        # 首充RB值 = amount / count，count为0时RB值为0
        avg_expr = case(
            (DailyStats.first_recharge_count > 0, DailyStats.first_recharge_amount / DailyStats.first_recharge_count),
            else_=0
        )

        count_stmt = select(func.count()).select_from(DailyStats)
        query_stmt = select(DailyStats).order_by(DailyStats.stat_date.desc())

        if start_date:
            count_stmt = count_stmt.where(DailyStats.stat_date >= start_date)
            query_stmt = query_stmt.where(DailyStats.stat_date >= start_date)
        if end_date:
            count_stmt = count_stmt.where(DailyStats.stat_date <= end_date)
            query_stmt = query_stmt.where(DailyStats.stat_date <= end_date)
        if invite_code:
            count_stmt = count_stmt.where(DailyStats.invite_code == invite_code)
            query_stmt = query_stmt.where(DailyStats.invite_code == invite_code)
        if avg_min is not None:
            count_stmt = count_stmt.where(avg_expr >= avg_min)
            query_stmt = query_stmt.where(avg_expr >= avg_min)
        if avg_max is not None:
            count_stmt = count_stmt.where(avg_expr <= avg_max)
            query_stmt = query_stmt.where(avg_expr <= avg_max)

        total = (await db.execute(count_stmt)).scalar() or 0
        p = get_pagination(page, page_size)
        result = await db.execute(query_stmt.offset(p["offset"]).limit(p["page_size"]))
        rows = result.scalars().all()

        data_list = [{
            "id": r.id,
            "stat_date": r.stat_date.strftime("%Y-%m-%d") if r.stat_date else None,
            "invite_code": r.invite_code,
            "register_count": r.register_count,
            "first_recharge_count": r.first_recharge_count,
            "first_recharge_amount": r.first_recharge_amount,
            "first_recharge_avg": round(r.first_recharge_amount / r.first_recharge_count) if r.first_recharge_count else 0,
        } for r in rows]

        return success_response(data=pagination_response(data_list, total, p["page"], p["page_size"]))
    except Exception as e:
        logger.error(f"查询每日统计失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="查询失败")


class CalculateRequest(BaseModel):
    stat_date: str


@router.post("/admin/daily-stats/calculate", summary="每日统计-手动统计")
@require_permission("marketing:view")
async def calculate_daily_stats(
    request: Request,
    body: CalculateRequest,
    db: AsyncSession = Depends(get_db),
):
    stat_date = body.stat_date

    try:
        # 1. 统计注册人数：按邀请码分组，从 player_invites.register_time
        reg_stmt = (
            select(
                PlayerInvite.invite_code,
                func.count().label('register_count'),
            )
            .where(PlayerInvite.register_time >= f"{stat_date} 00:00:00")
            .where(PlayerInvite.register_time <= f"{stat_date} 23:59:59")
            .group_by(PlayerInvite.invite_code)
        )
        reg_rows = (await db.execute(reg_stmt)).all()

        # 2. 统计首充人数和首充金额：first_recharges LEFT JOIN player_invites
        recharge_stmt = (
            select(
                PlayerInvite.invite_code,
                func.count().label('first_recharge_count'),
                func.coalesce(func.sum(FirstRecharge.amount), 0).label('first_recharge_amount'),
            )
            .outerjoin(PlayerInvite, FirstRecharge.player_id == PlayerInvite.player_id)
            .where(FirstRecharge.recharge_time >= f"{stat_date} 00:00:00")
            .where(FirstRecharge.recharge_time <= f"{stat_date} 23:59:59")
            .group_by(PlayerInvite.invite_code)
        )
        recharge_rows = (await db.execute(recharge_stmt)).all()

        # 3. 合并数据
        stats = {}
        for row in reg_rows:
            code = row.invite_code or '未知邀请码'
            stats[code] = {
                'stat_date': stat_date,
                'invite_code': code,
                'register_count': row.register_count,
                'first_recharge_count': 0,
                'first_recharge_amount': 0,
            }
        for row in recharge_rows:
            code = row.invite_code or '未知邀请码'
            if code in stats:
                stats[code]['first_recharge_count'] = row.first_recharge_count
                stats[code]['first_recharge_amount'] = int(row.first_recharge_amount)
            else:
                stats[code] = {
                    'stat_date': stat_date,
                    'invite_code': code,
                    'register_count': 0,
                    'first_recharge_count': row.first_recharge_count,
                    'first_recharge_amount': int(row.first_recharge_amount),
                }

        # 同一事务：先删除该日数据，再批量插入
        await db.execute(delete(DailyStats).where(DailyStats.stat_date == stat_date))
        if stats:
            await db.execute(insert(DailyStats), list(stats.values()))

        admin = request.state.admin
        await record_operation(db, admin["admin_id"], admin["username"], "marketing", "手动统计每日数据",
                               detail={"stat_date": stat_date, "count": len(stats)},
                               ip=get_client_ip(request))
        await db.commit()
        return success_response(data={"count": len(stats)}, message=f"统计完成，共生成 {len(stats)} 条记录")
    except Exception as e:
        logger.error(f"手动统计失败: {e}")
        await db.rollback()
        return error_response(code=ErrorCode.DATABASE_ERROR, message=f"统计失败: {str(e)}")
