from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from core.connection_password_cipher import ConnectionPasswordCipher
from repositories.text2sql_connection_repo import Text2SQLConnectionRepository
from schemas.text2sql import Text2SQLConnectionPayload, Text2SQLConnectionResponse


class Text2SQLConnectionService:
    """管理数据库连接配置、连通性测试和运行时引擎缓存。"""

    def __init__(self):
        """初始化引擎缓存。"""
        self._cached_engine: Engine | None = None
        self._cached_uri: str = ""
        self._password_cipher = ConnectionPasswordCipher()

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
        """把连接参数拼成 SQLAlchemy 可用的 MySQL URI。"""
        return (
            f"mysql+pymysql://{username}:{password}"
            f"@{host}:{port}/{database}?charset={charset}"
        )

    @staticmethod
    def _strip(value: str | None, fallback: str = "") -> str:
        """清理字符串参数，避免空值和多余空白。"""
        if value is None:
            return fallback
        return str(value).strip()

    def get_public_connection(self, db: Session) -> Text2SQLConnectionResponse:
        """返回前端可展示的连接配置（不带密码）。"""
        record = Text2SQLConnectionRepository(db).get_active()
        if record is None:
            return Text2SQLConnectionResponse(configured=False)
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
        """用 `SELECT 1` 验证目标 URI 是否可连接。"""
        engine = create_engine(uri, pool_pre_ping=True, pool_recycle=3600, echo=False)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        finally:
            engine.dispose()

    def _is_same_target(
        self,
        *,
        host: str | None,
        port: int | None,
        username: str | None,
        database: str | None,
        payload: Text2SQLConnectionPayload,
    ) -> bool:
        payload_host = self._strip(payload.host).lower()
        payload_port = int(payload.port or 3306)
        payload_username = self._strip(payload.username).lower()
        payload_database = self._strip(payload.database).lower()
        return (
            self._strip(host).lower() == payload_host
            and int(port or 3306) == payload_port
            and self._strip(username).lower() == payload_username
            and self._strip(database).lower() == payload_database
        )

    def _resolve_reusable_password(
        self,
        db: Session,
        payload: Text2SQLConnectionPayload,
        *,
        empty_password_error: str,
    ) -> str:
        """在密码留空时复用已保存连接密码，避免前端反复输入。"""
        current = Text2SQLConnectionRepository(db).get_active()
        if (
            current is not None
            and self._strip(current.password)
            and self._is_same_target(
                host=current.host,
                port=current.port,
                username=current.username,
                database=current.database,
                payload=payload,
            )
        ):
            decrypted = self._password_cipher.decrypt(current.password)
            return self._strip(decrypted)

        raise ValueError(empty_password_error)

    def test_connection(self, db: Session, payload: Text2SQLConnectionPayload) -> None:
        """测试连接参数是否可用。"""
        password = self._strip(payload.password)
        if not password:
            password = self._resolve_reusable_password(
                db,
                payload,
                empty_password_error="测试连接时 password 不能为空（仅当目标与已保存连接一致时可留空）",
            )
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
        """保存连接参数并刷新运行时引擎缓存。"""
        if payload.db_type != "mysql":
            raise ValueError("当前仅支持 mysql")
        repo = Text2SQLConnectionRepository(db)
        password = self._strip(payload.password)
        if not password:
            password = self._resolve_reusable_password(
                db,
                payload,
                empty_password_error="保存连接时 password 不能为空（修改目标后请重新输入密码）",
            )
        uri = self._build_uri(
            host=self._strip(payload.host),
            port=payload.port,
            username=self._strip(payload.username),
            password=password,
            database=self._strip(payload.database),
            charset=self._strip(payload.charset, "utf8mb4"),
        )
        self._test_uri(uri)
        encrypted_password = self._password_cipher.encrypt(password)
        repo.upsert(
            db_type="mysql",
            host=self._strip(payload.host),
            port=payload.port,
            username=self._strip(payload.username),
            password=encrypted_password,
            database=self._strip(payload.database),
            charset=self._strip(payload.charset, "utf8mb4"),
        )
        self._reset_engine_cache()
        return self.get_public_connection(db)

    def _resolve_runtime_uri(self, db: Session) -> str:
        """只从系统库已保存连接构建运行时 URI。"""
        record = Text2SQLConnectionRepository(db).get_active()
        if record is None:
            return ""
        decrypted_password = self._password_cipher.decrypt(record.password)
        return self._build_uri(
            host=record.host,
            port=record.port,
            username=record.username,
            password=decrypted_password,
            database=record.database,
            charset=record.charset,
        )

    def get_engine(self, db: Session) -> Engine:
        """返回可复用的 SQLAlchemy Engine。"""
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
        """销毁并清空当前引擎缓存。"""
        if self._cached_engine is not None:
            self._cached_engine.dispose()
        self._cached_engine = None
        self._cached_uri = ""
