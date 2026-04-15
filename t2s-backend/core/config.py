from typing import List

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """中文备注：封装Settings相关业务能力。
    类职责：聚合同类能力并提供统一调用入口。
    """
    PROJECT_NAME: str = "Text2SQL Server"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

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

    TEXT2SQL_ENABLED: bool = True
    TEXT2SQL_DB_URI: str = ""
    TEXT2SQL_MAX_ROWS: int = 50
    TEXT2SQL_READONLY: bool = True
    TEXT2SQL_EXEC_TIMEOUT_SECONDS: int = 20
    TEXT2SQL_AUTO_REPAIR_ROUNDS: int = 1
    TEXT2SQL_MAX_JOIN_TABLES: int = 5
    TEXT2SQL_QUERY_LOG_ENABLED: bool = True
    TABLE_ROUTE_MAX_CANDIDATES: int = 3
    TABLE_ROUTE_AMBIGUITY_DELTA: float = 0.15

    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_TIMEOUT: int = 120

    STARTUP_WAIT_ENABLED: bool = True
    STARTUP_WAIT_INTERVAL_SECONDS: int = 2

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """中文备注：处理database uri相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )

    @computed_field
    @property
    def EFFECTIVE_LLM_BASE_URL(self) -> str:
        """中文备注：处理llm base url相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return self.LLM_BASE_URL

    @computed_field
    @property
    def EFFECTIVE_LLM_API_KEY(self) -> str:
        """中文备注：处理llm api key相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return self.LLM_API_KEY

    @computed_field
    @property
    def EFFECTIVE_LLM_MODEL(self) -> str:
        """中文备注：处理llm model相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return self.LLM_MODEL

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
