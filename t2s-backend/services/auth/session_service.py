import hashlib
import json
import secrets

from core.config import settings
from core.redis_client import redis_client


class SessionService:
    PREFIX = "auth:session:"

    @staticmethod
    def _key(token: str) -> str:
        digest = hashlib.sha256(token.encode()).hexdigest()
        return f"{SessionService.PREFIX}{digest}"

    def create(self, user_id: int) -> str:
        token = secrets.token_urlsafe(48)

        redis_client.setex(
            self._key(token),
            settings.SESSION_TTL_SECONDS,
            json.dumps({"user_id": user_id}),
        )

        return token

    def get_user_id(self, token: str) -> int | None:
        raw = redis_client.get(self._key(token))
        if not raw:
            return None

        try:
            return int(json.loads(raw)["user_id"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def delete(self, token: str) -> None:
        redis_client.delete(self._key(token))


session_service = SessionService()
