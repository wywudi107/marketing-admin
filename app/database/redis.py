"""
Redis 连接模块
"""
import json
import redis.asyncio as aioredis
from loguru import logger

from app.config import config


class RedisDatabase:
    def __init__(self):
        self.redis: aioredis.Redis = None

    async def connect(self):
        try:
            redis_config = config.redis
            self.redis = aioredis.Redis(
                host=redis_config.get('host', '127.0.0.1'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                password=redis_config.get('password') or None,
                decode_responses=redis_config.get('decode_responses', True),
                max_connections=redis_config.get('max_connections', 50),
            )
            await self.redis.ping()
            logger.info(f"Redis 连接成功: {redis_config.get('host')}:{redis_config.get('port')}")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            raise

    async def disconnect(self):
        if self.redis:
            await self.redis.close()
            logger.info("Redis 连接已关闭")

    async def check_connection(self) -> bool:
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False

    # Token 管理
    async def set_admin_token(self, admin_id: int, token: str, expire: int = 28800):
        await self.redis.set(f"admin_token:{admin_id}", token, ex=expire)

    async def get_admin_token(self, admin_id: int) -> str:
        return await self.redis.get(f"admin_token:{admin_id}")

    async def delete_admin_token(self, admin_id: int):
        await self.redis.delete(f"admin_token:{admin_id}")

    async def get_token_ttl(self, admin_id: int) -> int:
        return await self.redis.ttl(f"admin_token:{admin_id}")

    async def refresh_admin_token(self, admin_id: int, expire: int = 28800):
        ttl = await self.get_token_ttl(admin_id)
        if 0 < ttl < 7200:  # 剩余不足2小时时续期
            await self.redis.expire(f"admin_token:{admin_id}", expire)

    # 登录失败计数
    async def incr_login_fail(self, username: str) -> int:
        key = f"admin_login_fail:{username}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 900)  # 15分钟过期
        return count

    async def get_login_fail_count(self, username: str) -> int:
        count = await self.redis.get(f"admin_login_fail:{username}")
        return int(count) if count else 0

    async def clear_login_fail(self, username: str):
        await self.redis.delete(f"admin_login_fail:{username}")

    # 分布式锁（与 game-hall 项目使用相同的 redis.lock() 实现）
    async def acquire_lock(self, key: str, wait_seconds: float = 10, lease_seconds: int = 60):
        """
        获取分布式锁

        Args:
            key: 锁的键名（会自动加 lock: 前缀）
            wait_seconds: 等待获取锁的超时时间（秒），0表示不等待
            lease_seconds: 锁的持有时间（秒），超时自动释放

        Returns:
            Lock对象（成功时），None（失败时）
        """
        try:
            lock_key = f"lock:{key}"
            lock = self.redis.lock(
                name=lock_key,
                timeout=lease_seconds,
                blocking_timeout=wait_seconds if wait_seconds > 0 else None
            )
            acquired = await lock.acquire(blocking=wait_seconds > 0)
            if acquired:
                return lock
            else:
                return None
        except Exception as e:
            logger.error(f"获取分布式锁异常: key={key}, error={e}")
            return None

    # 验证码
    async def set_captcha(self, captcha_id: str, answer: str, expire: int = 300):
        await self.redis.set(f"captcha:{captcha_id}", answer, ex=expire)

    async def get_and_delete_captcha(self, captcha_id: str) -> str:
        key = f"captcha:{captcha_id}"
        answer = await self.redis.get(key)
        if answer:
            await self.redis.delete(key)
        return answer

    # 在线用户数（读取 game-hall 的 Redis key）
    async def get_online_user_count(self) -> int:
        try:
            count = await self.redis.scard("ws:online_users")
            return count or 0
        except Exception:
            return 0


redis_db = RedisDatabase()
