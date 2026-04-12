from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

from core.config import settings
from repositories.text2sql_connection_repo import Text2SQLConnectionRepository
from schemas.text2sql import Text2SQLConnectionPayload, Text2SQLConnectionResponse


class Text2SQLConnectionService:
    def __init__(self):
        self._cached_engine: Engine | None = None
        self._cached_uri: str = ""

    @staticmethod
    def _build_uri(
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        charset: str,
    ) -> str:
        return (
            f"mysql+pymysql://{username}:{password}"
            f"@{host}:{port}/{database}?charset={charset}"
        )

    @staticmethod
    def _strip(value: str | None, fallback: str = "") -> str:
        if value is None:
            return fallback
        return str(value).strip()

    def _from_env(self) -> Text2SQLConnectionResponse:
        uri = self._strip(settings.TEXT2SQL_DB_URI)
        if not uri:
            return Text2SQLConnectionResponse(configured=False)

        parsed = make_url(uri)
        return Text2SQLConnectionResponse(
            configured=True,
            db_type="mysql",
            host=parsed.host or "",
            port=int(parsed.port or 3306),
            username=parsed.username or "",
            database=(parsed.database or ""),
            charset=parsed.query.get("charset", "utf8mb4"),
            has_password=bool(parsed.password),
        )

    def get_public_connection(self, db: Session) -> Text2SQLConnectionResponse:
        record = Text2SQLConnectionRepository(db).get_active()
        if record is None:
            return self._from_env()

        return Text2SQLConnectionResponse(
            configured=True,
            db_type="mysql",
            host=record.host,
            port=record.port,
            username=record.username,
            database=record.database,
            charset=record.charset,
            has_password=bool(record.password),
        )

    def _test_uri(self, uri: str) -> None:
        engine = create_engine(uri, pool_pre_ping=True, pool_recycle=3600, echo=False)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        finally:
            engine.dispose()

    def test_connection(self, payload: Text2SQLConnectionPayload) -> None:
        password = self._strip(payload.password)
        if not password:
            raise ValueError("测试连接时 password 不能为空")

        uri = self._build_uri(
            host=self._strip(payload.host),
            port=payload.port,
            username=self._strip(payload.username),
            password=password,
            database=self._strip(payload.database),
            charset=self._strip(payload.charset, "utf8mb4"),
        )
        self._test_uri(uri)

    def save_connection(self, db: Session, payload: Text2SQLConnectionPayload) -> Text2SQLConnectionResponse:
        if payload.db_type != "mysql":
            raise ValueError("当前仅支持 mysql")

        repo = Text2SQLConnectionRepository(db)
        current = repo.get_active()

        password = self._strip(payload.password)
        if not password and current is not None:
            password = current.password
        if not password:
            raise ValueError("保存连接时 password 不能为空")

        uri = self._build_uri(
            host=self._strip(payload.host),
            port=payload.port,
            username=self._strip(payload.username),
            password=password,
            database=self._strip(payload.database),
            charset=self._strip(payload.charset, "utf8mb4"),
        )
        self._test_uri(uri)

        repo.upsert(
            db_type="mysql",
            host=self._strip(payload.host),
            port=payload.port,
            username=self._strip(payload.username),
            password=password,
            database=self._strip(payload.database),
            charset=self._strip(payload.charset, "utf8mb4"),
        )

        self._reset_engine_cache()
        return self.get_public_connection(db)

    def _resolve_runtime_uri(self, db: Session) -> str:
        record = Text2SQLConnectionRepository(db).get_active()
        if record is not None:
            return self._build_uri(
                host=record.host,
                port=record.port,
                username=record.username,
                password=record.password,
                database=record.database,
                charset=record.charset,
            )
        return self._strip(settings.TEXT2SQL_DB_URI)

    def get_engine(self, db: Session) -> Engine:
        uri = self._resolve_runtime_uri(db)
        if not uri:
            raise RuntimeError("数据库连接未配置，请先在前端保存数据库连接")

        if self._cached_engine is None or self._cached_uri != uri:
            if self._cached_engine is not None:
                self._cached_engine.dispose()
            self._cached_engine = create_engine(uri, pool_pre_ping=True, pool_recycle=3600, echo=False)
            self._cached_uri = uri

        return self._cached_engine

    def _reset_engine_cache(self) -> None:
        if self._cached_engine is not None:
            self._cached_engine.dispose()
        self._cached_engine = None
        self._cached_uri = ""

