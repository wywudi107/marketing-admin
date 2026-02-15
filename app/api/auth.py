"""
管理员认证接口：登录/登出/个人信息/修改密码
"""
import base64
import io
import random
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.mysql import get_db
from app.database.redis import redis_db
from app.models.admin_user import AdminUser
from app.models.admin_role import AdminRole
from app.core.auth import verify_password, hash_password, create_access_token, get_current_admin, get_client_ip
from app.core.response import success_response, error_response, ErrorCode
from app.utils.log_helper import record_operation

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str
    captcha_id: str
    captcha_answer: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


def generate_captcha_image(text: str) -> str:
    """生成带干扰的验证码图片，返回 base64"""
    from PIL import ImageFilter

    width, height = 180, 60
    # 随机背景色（浅色）
    bg = (random.randint(220, 245), random.randint(220, 245), random.randint(220, 245))
    img = Image.new('RGB', (width, height), bg)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except (IOError, OSError):
        font = ImageFont.load_default(size=32)

    # 绘制干扰线（更粗更多）
    for _ in range(8):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        color = (random.randint(100, 180), random.randint(100, 180), random.randint(100, 180))
        draw.line([(x1, y1), (x2, y2)], fill=color, width=random.randint(1, 3))

    # 绘制干扰弧线
    for _ in range(4):
        x1, y1 = random.randint(-20, width), random.randint(-20, height)
        x2, y2 = x1 + random.randint(40, 120), y1 + random.randint(20, 60)
        color = (random.randint(80, 160), random.randint(80, 160), random.randint(80, 160))
        draw.arc([(x1, y1), (x2, y2)], 0, random.randint(180, 360), fill=color, width=2)

    # 绘制干扰点
    for _ in range(200):
        x, y = random.randint(0, width - 1), random.randint(0, height - 1)
        color = (random.randint(80, 200), random.randint(80, 200), random.randint(80, 200))
        draw.point((x, y), fill=color)

    # 逐字符绘制（带随机偏移和旋转）
    x_offset = 8
    for char in text:
        char_img = Image.new('RGBA', (36, 44), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_color = (random.randint(10, 80), random.randint(10, 80), random.randint(10, 80))
        char_draw.text((2, 2), char, font=font, fill=char_color)
        # 随机旋转
        angle = random.randint(-15, 15)
        char_img = char_img.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))
        y_offset = random.randint(2, 12)
        img.paste(char_img, (x_offset, y_offset), char_img)
        x_offset += random.randint(18, 24)

    # 高斯模糊
    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


@router.get("/admin/captcha", summary="获取登录验证码")
async def get_captcha():
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    op = random.choice(['+', '-'])
    if op == '-' and a < b:
        a, b = b, a
    answer = str(a + b) if op == '+' else str(a - b)
    question = f"{a} {op} {b} = ?"
    captcha_id = str(uuid.uuid4())
    await redis_db.set_captcha(captcha_id, answer)
    image_base64 = generate_captcha_image(question)
    return success_response(data={"captcha_id": captcha_id, "image": f"data:image/png;base64,{image_base64}"})


@router.post("/admin/login", summary="管理员登录")
async def admin_login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        client_ip = get_client_ip(request)

        # 校验验证码
        correct_answer = await redis_db.get_and_delete_captcha(body.captcha_id)
        if not correct_answer or correct_answer != body.captcha_answer.strip():
            return error_response(code=ErrorCode.INVALID_CAPTCHA, message="验证码错误")

        # 检查登录失败次数
        fail_count = await redis_db.get_login_fail_count(body.username)
        if fail_count >= 5:
            return error_response(code=ErrorCode.ACCOUNT_LOCKED, message="账号已锁定，请15分钟后重试")

        # 查询管理员
        result = await db.execute(select(AdminUser).where(AdminUser.username == body.username))
        admin = result.scalar_one_or_none()
        if not admin:
            await redis_db.incr_login_fail(body.username)
            return error_response(code=ErrorCode.INVALID_CREDENTIALS, message="用户名或密码错误")

        # 验证密码
        if not verify_password(body.password, admin.password):
            await redis_db.incr_login_fail(body.username)
            return error_response(code=ErrorCode.INVALID_CREDENTIALS, message="用户名或密码错误")

        # 检查状态
        if admin.status != 1:
            return error_response(code=ErrorCode.USER_DISABLED, message="账号已禁用")

        # 查询角色
        role_result = await db.execute(select(AdminRole).where(AdminRole.id == admin.role_id))
        role = role_result.scalar_one_or_none()
        if not role or role.status != 1:
            return error_response(code=ErrorCode.PERMISSION_DENIED, message="角色无效或已禁用")

        permissions = role.permissions or []

        # 生成 Token
        token_data = {
            "admin_id": admin.id,
            "username": admin.username,
            "role_key": role.role_key,
            "permissions": permissions,
        }
        token = create_access_token(token_data)

        # 存储到 Redis
        await redis_db.set_admin_token(admin.id, token)
        await redis_db.clear_login_fail(body.username)

        # 更新登录信息
        admin.last_login_at = datetime.now()
        admin.last_login_ip = client_ip
        await db.commit()

        logger.info(f"管理员登录成功: {admin.username} (ID:{admin.id}) IP:{client_ip}")

        return success_response(data={
            "token": token,
            "admin_info": {
                "id": admin.id,
                "username": admin.username,
                "nickname": admin.nickname,
                "role_name": role.role_name,
                "role_key": role.role_key,
                "permissions": permissions,
            }
        })
    except Exception as e:
        logger.error(f"管理员登录失败: {e}")
        return error_response(code=ErrorCode.DATABASE_ERROR, message="登录失败")


@router.post("/admin/logout", summary="管理员登出")
async def admin_logout(request: Request):
    admin = await get_current_admin(request)
    if not admin:
        return error_response(code=ErrorCode.UNAUTHORIZED, message="未登录")

    await redis_db.delete_admin_token(admin["admin_id"])
    logger.info(f"管理员登出: {admin['username']}")
    return success_response(message="已登出")


@router.get("/admin/profile", summary="获取当前管理员信息")
async def get_profile(request: Request, db: AsyncSession = Depends(get_db)):
    admin = await get_current_admin(request)
    if not admin:
        return error_response(code=ErrorCode.UNAUTHORIZED, message="未登录或Token已过期")

    result = await db.execute(select(AdminUser).where(AdminUser.id == admin["admin_id"]))
    admin_user = result.scalar_one_or_none()
    if not admin_user:
        return error_response(code=ErrorCode.USER_NOT_FOUND, message="管理员不存在")

    role_result = await db.execute(select(AdminRole).where(AdminRole.id == admin_user.role_id))
    role = role_result.scalar_one_or_none()

    return success_response(data={
        "id": admin_user.id,
        "username": admin_user.username,
        "nickname": admin_user.nickname,
        "role_name": role.role_name if role else None,
        "role_key": role.role_key if role else None,
        "permissions": role.permissions if role else [],
        "last_login_at": admin_user.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if admin_user.last_login_at else None,
        "last_login_ip": admin_user.last_login_ip,
    })


@router.put("/admin/password", summary="修改当前管理员密码")
async def change_password(request: Request, body: ChangePasswordRequest, db: AsyncSession = Depends(get_db)):
    admin = await get_current_admin(request)
    if not admin:
        return error_response(code=ErrorCode.UNAUTHORIZED, message="未登录或Token已过期")

    result = await db.execute(select(AdminUser).where(AdminUser.id == admin["admin_id"]))
    admin_user = result.scalar_one_or_none()
    if not admin_user:
        return error_response(code=ErrorCode.USER_NOT_FOUND, message="管理员不存在")

    if not verify_password(body.old_password, admin_user.password):
        return error_response(code=ErrorCode.INVALID_CREDENTIALS, message="原密码错误")

    if len(body.new_password) < 6:
        return error_response(code=ErrorCode.INVALID_PARAMETER, message="新密码长度不能少于6位")

    admin_user.password = hash_password(body.new_password)
    await record_operation(db, admin["admin_id"], admin["username"], "system", "修改密码", ip=get_client_ip(request))
    await db.commit()

    # 清除 token，要求重新登录
    await redis_db.delete_admin_token(admin["admin_id"])

    return success_response(message="密码修改成功，请重新登录")
