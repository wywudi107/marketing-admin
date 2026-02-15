"""
游戏大厅后台管理系统 - FastAPI 入口
"""
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import config
from app.database.mysql import mysql_db
from app.database.redis import redis_db

# 日志配置
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}", level="INFO")
logger.add("logs/admin_{time:YYYY-MM-DD}.log", rotation="00:00", retention="30 days", level="DEBUG")
logger.add("logs/error_{time:YYYY-MM-DD}.log", rotation="00:00", retention="30 days", level="ERROR")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("正在启动后台管理系统...")
    await mysql_db.connect()
    await redis_db.connect()
    logger.info("后台管理系统启动完成")
    yield
    logger.info("正在关闭后台管理系统...")
    await mysql_db.disconnect()
    await redis_db.disconnect()
    logger.info("后台管理系统已关闭")


app = FastAPI(
    title="游戏大厅后台管理系统",
    description="后台管理系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.app.get('cors_origins', ['*']),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.api import auth, admin, log

app.include_router(auth.router, tags=["认证"])
app.include_router(admin.router, tags=["管理员管理"])
app.include_router(log.router, tags=["操作日志"])


@app.get("/health", summary="健康检查")
async def health_check():
    mysql_status = await mysql_db.check_connection()
    redis_status = await redis_db.check_connection()
    return {
        "status": "healthy" if (mysql_status and redis_status) else "unhealthy",
        "mysql": "connected" if mysql_status else "disconnected",
        "redis": "connected" if redis_status else "disconnected",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config.app.get('host', '0.0.0.0'),
        port=config.app.get('port', 8001),
        reload=config.app.get('debug', False),
    )
