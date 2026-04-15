from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

from core.config import settings
from repositories.text2sql_connection_repo import Text2SQLConnectionRepository
from schemas.text2sql import Text2SQLConnectionPayload, Text2SQLConnectionResponse


class Text2SQLConnectionService:
    """中文备注：封装连接管理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(self):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self._cached_engine: Engine | None`。
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
        """中文备注：构建uri相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return (
            f"mysql+pymysql://{username}:{password}"
            f"@{host}:{port}/{database}?charset={charset}"
        )

    @staticmethod
    def _strip(value: str | None, fallback: str = "") -> str:
        """中文备注：清理相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if value is None:
            return fallback
        # 2. 返回结果：输出当前函数最终结果。
        return str(value).strip()

    def _from_env(self) -> Text2SQLConnectionResponse:
        """中文备注：处理env相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `uri`。
        uri = self._strip(settings.TEXT2SQL_DB_URI)
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if not uri:
            return Text2SQLConnectionResponse(configured=False)

        # 3. 变量构建：计算并更新 `parsed`。
        parsed = make_url(uri)
        # 4. 返回结果：输出当前函数最终结果。
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
        """中文备注：获取public connection相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `record`。
        record = Text2SQLConnectionRepository(db).get_active()
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if record is None:
            return self._from_env()

        # 3. 返回结果：输出当前函数最终结果。
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
        """中文备注：测试uri相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 引擎与反射能力初始化：准备数据库连接和元数据提取能力。
        engine = create_engine(uri, pool_pre_ping=True, pool_recycle=3600, echo=False)
        # 2. 核心处理：执行当前阶段的业务逻辑。
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
        """中文备注：解析可复用password相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
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
            return self._strip(current.password)

        env_uri = self._strip(settings.TEXT2SQL_DB_URI)
        if env_uri:
            parsed = make_url(env_uri)
            if parsed.password and self._is_same_target(
                host=parsed.host,
                port=parsed.port,
                username=parsed.username,
                database=parsed.database,
                payload=payload,
            ):
                return self._strip(str(parsed.password))

        raise ValueError(empty_password_error)

    def test_connection(self, db: Session, payload: Text2SQLConnectionPayload) -> None:
        """中文备注：测试connection相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `password`。
        password = self._strip(payload.password)
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if not password:
            password = self._resolve_reusable_password(
                db,
                payload,
                empty_password_error="测试连接时 password 不能为空（仅当目标与已保存连接一致时可留空）",
            )

        # 3. 变量构建：计算并更新 `uri`。
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
        """中文备注：保存connection相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if payload.db_type != "mysql":
            raise ValueError("当前仅支持 mysql")

        # 2. 变量构建：计算并更新 `repo`。
        repo = Text2SQLConnectionRepository(db)

        # 3. 变量构建：计算并更新 `password`。
        password = self._strip(payload.password)
        # 4. 条件分支：根据当前状态选择不同处理路径。
        if not password:
            password = self._resolve_reusable_password(
                db,
                payload,
                empty_password_error="保存连接时 password 不能为空（修改目标后请重新输入密码）",
            )

        # 6. 变量构建：计算并更新 `uri`。
        uri = self._build_uri(
            host=self._strip(payload.host),
            port=payload.port,
            username=self._strip(payload.username),
            password=password,
            database=self._strip(payload.database),
            charset=self._strip(payload.charset, "utf8mb4"),
        )
        self._test_uri(uri)

        # 7. 核心处理：执行当前阶段的业务逻辑。
        repo.upsert(
            db_type="mysql",
            host=self._strip(payload.host),
            port=payload.port,
            username=self._strip(payload.username),
            password=password,
            database=self._strip(payload.database),
            charset=self._strip(payload.charset, "utf8mb4"),
        )

        # 8. 核心处理：执行当前阶段的业务逻辑。
        self._reset_engine_cache()
        # 9. 返回结果：输出当前函数最终结果。
        return self.get_public_connection(db)

    def _resolve_runtime_uri(self, db: Session) -> str:
        """中文备注：解析runtime uri相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `record`。
        record = Text2SQLConnectionRepository(db).get_active()
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if record is not None:
            return self._build_uri(
                host=record.host,
                port=record.port,
                username=record.username,
                password=record.password,
                database=record.database,
                charset=record.charset,
            )
        # 3. 返回结果：输出当前函数最终结果。
        return self._strip(settings.TEXT2SQL_DB_URI)

    def get_engine(self, db: Session) -> Engine:
        """中文备注：获取engine相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 目标解析与合法性校验：解析输入范围并拦截非法数据。
        uri = self._resolve_runtime_uri(db)
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if not uri:
            raise RuntimeError("数据库连接未配置，请先在前端保存数据库连接")

        # 3. 条件分支：根据当前状态选择不同处理路径。
        if self._cached_engine is None or self._cached_uri != uri:
            if self._cached_engine is not None:
                self._cached_engine.dispose()
            self._cached_engine = create_engine(uri, pool_pre_ping=True, pool_recycle=3600, echo=False)
            self._cached_uri = uri

        # 4. 返回结果：输出当前函数最终结果。
        return self._cached_engine

    def _reset_engine_cache(self) -> None:
        """中文备注：处理engine cache相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if self._cached_engine is not None:
            self._cached_engine.dispose()
        self._cached_engine = None
        self._cached_uri = ""

