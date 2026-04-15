from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.text2sql_connection import Text2SQLConnection


class Text2SQLConnectionRepository:
    """中文备注：封装连接管理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(self, db: Session):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self.db`。
        self.db = db

    def get_active(self) -> Text2SQLConnection | None:
        """中文备注：获取active相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
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
        """中文备注：处理相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `record`。
        record = self.get_active()
        # 2. 条件分支：根据当前状态选择不同处理路径。
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

        # 3. 外部调用：执行数据库或接口调用并接收返回值。
        self.db.commit()
        self.db.refresh(record)
        # 4. 返回结果：输出当前函数最终结果。
        return record

