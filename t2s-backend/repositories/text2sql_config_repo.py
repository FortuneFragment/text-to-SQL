from sqlalchemy.orm import Session

from models.text2sql_config import Text2SQLConfig


class Text2SQLConfigRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: int) -> Text2SQLConfig | None:
        return (
            self.db.query(Text2SQLConfig)
            .filter(
                Text2SQLConfig.user_id == user_id,
                Text2SQLConfig.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    def upsert(
        self,
        user_id: int,
        selected_tables: str | None,
        prompt_hint: str | None,
    ) -> Text2SQLConfig:
        config = self.get_by_user_id(user_id)
        if config is None:
            config = Text2SQLConfig(
                user_id=user_id,
                selected_tables=selected_tables,
                prompt_hint=prompt_hint,
                is_deleted=False,
            )
            self.db.add(config)
        else:
            config.selected_tables = selected_tables
            config.prompt_hint = prompt_hint
            config.is_deleted = False

        self.db.commit()
        self.db.refresh(config)
        return config

