from sqlalchemy.orm import Session

from models.text2sql_scoped_config import Text2SQLScopedConfig


class Text2SQLScopedConfigRepository:
    """负责按连接维度保存 Text2SQL 配置。"""

    def __init__(self, db: Session):
        """注入数据库会话。"""
        self.db = db

    def get_by_user_and_connection(self, user_id: int, connection_key: str) -> Text2SQLScopedConfig | None:
        """按用户和连接键读取配置记录。"""
        return (
            self.db.query(Text2SQLScopedConfig)
            .filter(
                Text2SQLScopedConfig.user_id == user_id,
                Text2SQLScopedConfig.connection_key == connection_key,
                Text2SQLScopedConfig.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    def upsert(
        self,
        *,
        user_id: int,
        connection_key: str,
        prompt_hint: str | None,
    ) -> Text2SQLScopedConfig:
        """按用户+连接键创建或更新配置记录。"""
        config = self.get_by_user_and_connection(user_id, connection_key)
        if config is None:
            config = Text2SQLScopedConfig(
                user_id=user_id,
                connection_key=connection_key,
                prompt_hint=prompt_hint,
                is_deleted=False,
            )
            self.db.add(config)
        else:
            config.prompt_hint = prompt_hint
            config.is_deleted = False
        self.db.commit()
        self.db.refresh(config)
        return config
