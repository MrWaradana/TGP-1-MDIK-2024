from pydantic import BaseSettings

class RedisSettings(BaseSettings):
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 1000
    CACHE_EXPIRATION_MINUTES: int = 30

    class Config:
        env_prefix = "REDIS_"

redis_settings = RedisSettings()