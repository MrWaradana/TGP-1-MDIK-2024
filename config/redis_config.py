from pydantic import BaseSettings


class RedisSettings(BaseSettings):
    REDIS_HOST: str = "redis-16912.c292.ap-southeast-1-1.ec2.redns.redis-cloud.com"
    REDIS_PORT: int = 16912
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 1000
    CACHE_EXPIRATION_MINUTES: int = 30

    class Config:
        env_prefix = "REDIS_"


redis_settings = RedisSettings()
