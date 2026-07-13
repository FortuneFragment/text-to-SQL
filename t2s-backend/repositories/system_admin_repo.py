from sqlalchemy.orm import Session

from models.system_admin_whitelist import SystemAdminWhitelist


class SystemAdminRepository:
    def __init__(self, db: Session):
        self.db = db

    def is_enabled(self, uni_code: str) -> bool:
        return (
            self.db.query(SystemAdminWhitelist)
            .filter(
                SystemAdminWhitelist.uni_code == uni_code,
                SystemAdminWhitelist.enabled.is_(True),
            )
            .first()
            is not None
        )
