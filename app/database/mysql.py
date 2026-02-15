"""
MySQL 数据库连接模块
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from loguru import logger

from app.config import config

Base = declarative_base()


class MySQLDatabase:
    def __init__(self):
        self.engine: AsyncEngine = None
        self.async_session_maker: sessionmaker = None

    async def connect(self):
        try:
            db_config = config.database
            database_url = (
                f"mysql+aiomysql://{db_config['user']}:{db_config['password']}"
                f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
                f"?charset={db_config.get('charset', 'utf8mb4')}"
            )
            self.engine = create_async_engine(
                database_url,
                echo=config.app.get('debug', False),
                pool_size=db_config.get('pool_size', 10),
                max_overflow=db_config.get('max_overflow', 20),
                pool_recycle=db_config.get('pool_recycle', 3600),
                pool_pre_ping=True,
            )
            self.async_session_maker = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False
            )
            logger.info(f"MySQL 连接池已创建: {db_config['host']}:{db_config['port']}/{db_config['database']}")
        except Exception as e:
            logger.error(f"MySQL 连接失败: {e}")
            raise

    async def disconnect(self):
        if self.engine:
            await self.engine.dispose()
            logger.info("MySQL 连接池已释放")

    async def check_connection(self) -> bool:
        try:
            from sqlalchemy import text
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"MySQL 连接检查失败: {e}")
            return False

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        if self.async_session_maker is None:
            raise RuntimeError("数据库未初始化，请先调用 connect() 方法")
        session = self.async_session_maker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


mysql_db = MySQLDatabase()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with mysql_db.get_session() as session:
        yield session
