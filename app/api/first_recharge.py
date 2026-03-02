"""
首充列表接口 - 导入、分页查询、批量删除
"""
from fastapi import APIRouter, Depends, Request, Query, UploadFile, File
from pydantic import BaseModel
from typing import List
from sqlalchemy import select, func, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from io import BytesIO

from app.database.mysql import get_db
from app.models.first_recharge import FirstRecharge
from app.core.permission import require_permission
from app.core.auth import get_client_ip
from app.core.response import success_response, error_response, ErrorCode
from app.utils.pagination import get_pagination, pagination_response
from app.utils.log_helper import record_operation

router = APIRouter()


@router.get("/admin/first-recharges", summary="首充列表-分页查询")
@require_permission("marketing:view")
async def get_first_recharges(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    try:
        count_stmt = select(func.count()).select_from(FirstRecharge)
        query_stmt = select(FirstRecharge).order_by(FirstRecharge.recharge_time.desc())

        if start_date:
            count_stmt = count_stmt.where(FirstRecharge.recharge_time >= f"{start_date} 00:00:00")
            query_stmt = query_stmt.where(FirstRecharge.recharge_time >= f"{start_date} 00:00:00")
        if end_date:
            count_stmt = count_stmt.where(FirstRecharge.recharge_time <= f"{end_date} 23:59:59")
            query_stmt = query_stmt.where(FirstRecharge.recharge_time <= f"{end_date} 23:59:59")

        total = (await db.execute(count_stmt)).scalar() or 0
        p = get_pagination(page, page_size)
        result = await db.execute(query_stmt.offset(p["offset"]).limit(p["page_size"]))
        rows = result.scalars().all()

        data_list = [{
            "id": r.id,
            "player_id": r.player_id,
            "order_no": r.order_no,
            "channel": r.channel,
            "nickname": r.nickname,
            "amount": r.amount,
            "pay_method": r.pay_method,
            "recharge_time": r.recharge_time.strftime("%Y-%m-%d %H:%M:%S") if r.recharge_time else None,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
        } for r in rows]

        return success_response(data=pagination_response(data_list, total, p["page"], p["page_size"]))
    except Exception as e:
        logger.error(f"查询首充列表失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="查询失败")


@router.post("/admin/first-recharges/import", summary="首充列表-导入Excel")
@require_permission("marketing:view")
async def import_first_recharges(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        return error_response(code=ErrorCode.INVALID_PARAMETER, message="仅支持 .xlsx/.xls 文件")

    try:
        import openpyxl

        contents = await file.read()
        wb = openpyxl.load_workbook(BytesIO(contents), read_only=True)
        ws = wb.active

        rows_data = []
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or not row[0]:
                continue
            # 跳过非数字的玩家ID（如末尾的"共 105645 条"等总结行）
            if not isinstance(row[0], (int, float)):
                continue
            player_id = str(int(row[0]))
            order_no = str(int(row[1])) if isinstance(row[1], float) else str(row[1]).strip()
            channel = str(row[2]).strip() if row[2] else None
            nickname = str(int(row[3])) if isinstance(row[3], (int, float)) else (str(row[3]).strip() if row[3] else None)
            amount = int(row[4]) if row[4] else 0
            pay_method = str(row[5]).strip() if row[5] else None
            recharge_time = row[6] if row[6] else None

            rows_data.append({
                "player_id": player_id,
                "order_no": order_no,
                "channel": channel,
                "nickname": nickname,
                "amount": amount,
                "pay_method": pay_method,
                "recharge_time": recharge_time,
            })

        wb.close()

        if not rows_data:
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="文件中没有有效数据")

        # 批量插入，每 500 条一批
        batch_size = 500
        for i in range(0, len(rows_data), batch_size):
            await db.execute(insert(FirstRecharge), rows_data[i:i + batch_size])

        admin = request.state.admin
        await record_operation(db, admin["admin_id"], admin["username"], "marketing", "导入首充列表",
                               detail={"filename": file.filename, "count": len(rows_data)},
                               ip=get_client_ip(request))
        await db.commit()
        return success_response(data={"count": len(rows_data)}, message=f"成功导入 {len(rows_data)} 条记录")
    except Exception as e:
        logger.error(f"导入首充列表失败: {e}")
        await db.rollback()
        return error_response(code=ErrorCode.DATABASE_ERROR, message=f"导入失败: {str(e)}")


class BatchDeleteRequest(BaseModel):
    ids: List[int]


@router.post("/admin/first-recharges/delete", summary="首充列表-批量删除")
@require_permission("marketing:view")
async def batch_delete_first_recharges(
    request: Request,
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        if not body.ids:
            return error_response(code=ErrorCode.INVALID_PARAMETER, message="请选择要删除的记录")

        result = await db.execute(delete(FirstRecharge).where(FirstRecharge.id.in_(body.ids)))
        deleted_count = result.rowcount

        admin = request.state.admin
        await record_operation(db, admin["admin_id"], admin["username"], "marketing", "批量删除首充记录",
                               detail={"ids": body.ids, "deleted_count": deleted_count},
                               ip=get_client_ip(request))
        await db.commit()
        return success_response(data={"deleted_count": deleted_count}, message=f"成功删除 {deleted_count} 条记录")
    except Exception as e:
        logger.error(f"批量删除首充记录失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="删除失败")
