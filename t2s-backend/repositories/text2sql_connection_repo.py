from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.text2sql_connection import Text2SQLConnection


class Text2SQLConnectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active(self) -> Text2SQLConnection | None:
        return self.db.query(Text2SQLConnection).order_by(desc(Text2SQLConnection.updated_at)).first()

    def upsert(
        self,
        *,
        db_type: str,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        charset: str,
    ) -> Text2SQLConnection:
        record = self.get_active()
        if record is None:
            record = Text2SQLConnection(
                db_type=db_type,
                host=host,
                port=port,
                username=username,
                password=password,
                database=database,
                charset=charset,
            )
            self.db.add(record)
        else:
            record.db_type = db_type
            record.host = host
            record.port = port
            record.username = username
            record.password = password
            record.database = database
            record.charset = charset

        self.db.commit()
        self.db.refresh(record)
        return record

