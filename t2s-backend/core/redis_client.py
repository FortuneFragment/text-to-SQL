from redis import Redis

from core.config import settings


redis_client = Redis.from_url(
    settings.EFFECTIVE_REDIS_URL,
    decode_responses=True,
)
