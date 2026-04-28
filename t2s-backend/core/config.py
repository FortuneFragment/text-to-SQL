from typing import List
from urllib.parse import quote_plus

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Text2SQL Server"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    APP_SECRET_KEY: str = ""
    FERNET_KEY: str = ""

    CORS_ORIGINS: List[str] = ["*"]

    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_HOST: str
    MYSQL_PORT: str
    MYSQL_DB: str

    REDIS_HOST: str
    REDIS_PORT: str
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_NAME: str = "qa-knowledge-files"

    MILVUS_HOST: str = "127.0.0.1"
    MILVUS_PORT: int = 19530
    MILVUS_VECTOR_DIM: int = 1024
    MILVUS_COLLECTION: str = "text2sql_kb"
    MAX_UPLOAD_FILE_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: List[str] = [
        "txt",
        "md",
        "markdown",
        "csv",
        "json",
        "yaml",
        "yml",
        "sql",
        "log",
    ]

    TEXT2SQL_ENABLED: bool = True
    TEXT2SQL_MAX_ROWS: int = 50
    TEXT2SQL_READONLY: bool = True
    TEXT2SQL_EXEC_TIMEOUT_SECONDS: int = 20
    TEXT2SQL_AUTO_REPAIR_ROUNDS: int = 2
    TEXT2SQL_MULTI_TABLE_ENABLED: bool = True
    TEXT2SQL_MAX_JOIN_TABLES: int = 5
    TEXT2SQL_QUERY_LOG_ENABLED: bool = True
    TEXT2SQL_ENUM_HINT_ENABLED: bool = True
    TEXT2SQL_ENUM_HINT_SAMPLE_ROWS: int = 100
    TEXT2SQL_ENUM_HINT_TOP_VALUES: int = 5
    TEXT2SQL_ENUM_HINT_MAX_COLUMNS_PER_TABLE: int = 6
    TEXT2SQL_ENUM_HINT_MAX_WORKERS: int = 4
    TEXT2SQL_ENUM_HINT_PROBE_TIMEOUT_MS: int = 300
    TEXT2SQL_ENUM_HINT_MAX_PROMPT_CHARS: int = 2400
    TEXT2SQL_ENUM_HINT_MAX_TABLES: int = 3
    TABLE_ROUTE_KB_ID: int = 2
    TABLE_ROUTE_KB_SEARCH_TOP_K: int = 120
    TABLE_ROUTE_KB_RECALL_CANDIDATES: int = 60
    TABLE_ROUTE_MAX_CANDIDATES: int = 10
    TABLE_ROUTE_AMBIGUITY_DELTA: float = 0.15
    TABLE_ROUTE_SEMANTIC_SCORE_WEIGHT: float = 10.0
    TABLE_ROUTE_KEYWORD_SCORE_WEIGHT: float = 1.0
    TABLE_ROUTE_PROFILE_SCORE_WEIGHT: float = 2.0
    TABLE_ROUTE_NAME_EXACT_MATCH_SCORE: float = 2.0
    TABLE_ROUTE_NAME_TOKEN_MATCH_SCORE: float = 0.85
    TABLE_ROUTE_PROFILE_TOKEN_MATCH_SCORE: float = 0.18
    TABLE_ROUTE_PROFILE_SCORE_CAP: float = 3.0

    KB_ENABLED: bool = True
    KB_ASYNC_ENABLED: bool = True
    KB_ASYNC_BACKEND: str = "celery"
    KB_QUEUE_NAME: str = "text2sql-kb"
    KB_TASK_TIMEOUT_SECONDS: int = 1800
    KB_CHUNK_SIZE: int = 800
    KB_CHUNK_OVERLAP: int = 120

    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = ""
    EMBEDDING_TIMEOUT_SECONDS: int = 60

    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_TASK_ALWAYS_EAGER: bool = False

    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_TIMEOUT: int = 120

    STARTUP_WAIT_ENABLED: bool = True
    STARTUP_WAIT_INTERVAL_SECONDS: int = 2
    STARTUP_WAIT_MILVUS: bool = True
    STARTUP_WAIT_MINIO: bool = True

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """处理SQLALCHEMY_DATABASE_URI相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )

    @computed_field
    @property
    def EFFECTIVE_LLM_BASE_URL(self) -> str:
        """处理EFFECTIVE_LLM_BASE_URL相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        return self.LLM_BASE_URL

    @computed_field
    @property
    def EFFECTIVE_LLM_API_KEY(self) -> str:
        """处理EFFECTIVE_LLM_API_KEY相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        return self.LLM_API_KEY

    @computed_field
    @property
    def EFFECTIVE_LLM_MODEL(self) -> str:
        """处理EFFECTIVE_LLM_MODEL相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        return self.LLM_MODEL

    @computed_field
    @property
    def EFFECTIVE_REDIS_URL(self) -> str:
        """处理EFFECTIVE_REDIS_URL相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        password = quote_plus(self.REDIS_PASSWORD) if self.REDIS_PASSWORD else ""
        auth = f":{password}@" if password else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @computed_field
    @property
    def EFFECTIVE_CELERY_BROKER_URL(self) -> str:
        """处理EFFECTIVE_CELERY_BROKER_URL相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        return self.CELERY_BROKER_URL or self.EFFECTIVE_REDIS_URL

    @computed_field
    @property
    def EFFECTIVE_CELERY_RESULT_BACKEND(self) -> str:
        """处理EFFECTIVE_CELERY_RESULT_BACKEND相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        return self.CELERY_RESULT_BACKEND or self.EFFECTIVE_REDIS_URL

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
