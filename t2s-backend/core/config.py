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

    # Elasticsearch vector knowledge base
    ES_HOST: str = "127.0.0.1"
    ES_PORT: int = 9200
    ES_URL: str = ""
    ES_INDEX_NAME: str = "text2sql-kb"
    ES_VECTOR_DIM: int = 1024
    ES_REQUEST_TIMEOUT_SECONDS: int = 30
    ES_KNN_NUM_CANDIDATES: int = 200
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
    TEXT2SQL_SELF_CONSISTENCY_N: int = 1
    TEXT2SQL_SELF_CONSISTENCY_TEMPERATURE: float = 0.4
    TEXT2SQL_MULTI_TABLE_ENABLED: bool = True
    TEXT2SQL_MAX_JOIN_TABLES: int = 5
    TEXT2SQL_QUERY_LOG_ENABLED: bool = True
    TEXT2SQL_FEW_SHOT_ENABLED: bool = False
    TEXT2SQL_FEWSHOT_MIN_SCORE: int = 5
    FEW_SHOT_KB_ID: int = 0
    DATA_DICTIONARY_KB_ID: int = 0
    TEXT2SQL_SCHEMA_PRUNE_ENABLED: bool = False
    TEXT2SQL_SCHEMA_MAX_COLS_PER_TABLE: int = 80
    TEXT2SQL_SCHEMA_PRUNE_KEEP_COLS: int = 40
    TEXT2SQL_ENUM_HINT_ENABLED: bool = True
    TEXT2SQL_ENUM_HINT_SAMPLE_ROWS: int = 100
    TEXT2SQL_ENUM_HINT_TOP_VALUES: int = 5
    TEXT2SQL_ENUM_HINT_MAX_COLUMNS_PER_TABLE: int = 6
    TEXT2SQL_ENUM_HINT_MAX_WORKERS: int = 4
    TEXT2SQL_ENUM_HINT_PROBE_TIMEOUT_MS: int = 300
    TEXT2SQL_ENUM_HINT_MAX_PROMPT_CHARS: int = 2400
    TEXT2SQL_ENUM_HINT_MAX_TABLES: int = 3
    # 码值字典：编码注入（生成前）与解码替换（查询后）
    TEXT2SQL_CODE_HINT_ENABLED: bool = True
    TEXT2SQL_CODE_HINT_SMALL_DICT_MAX: int = 50
    TEXT2SQL_CODE_HINT_MAX_VALUES_PER_CATEGORY: int = 50
    TEXT2SQL_CODE_DECODE_ENABLED: bool = True
    TEXT2SQL_CODE_DECODE_MAX_ROWS: int = 2000
    TABLE_ROUTE_KB_ID: int = 2
    TEXT2SQL_TABLE_DESC_KB_NAME: str = "table_desc"
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

    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_TASK_ALWAYS_EAGER: bool = False

    STARTUP_WAIT_ENABLED: bool = True
    STARTUP_WAIT_INTERVAL_SECONDS: int = 2
    STARTUP_WAIT_TIMEOUT_SECONDS: int = 120
    STARTUP_WAIT_ES: bool = True
    STARTUP_WAIT_MINIO: bool = True

    @computed_field
    @property
    def EFFECTIVE_ES_URL(self) -> str:
        url = str(self.ES_URL or "").strip()
        if url:
            return url
        return f"http://{self.ES_HOST}:{self.ES_PORT}"

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
