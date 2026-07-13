from datetime import datetime

from sqlalchemy.orm import Session

from models.system_user import SystemUser


class SystemUserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> SystemUser | None:
        return self.db.get(SystemUser, user_id)

    def get_by_uni_code(self, uni_code: str) -> SystemUser | None:
        return (
            self.db.query(SystemUser)
            .filter(SystemUser.uni_code == uni_code)
            .first()
        )

    def upsert(
        self,
        *,
        uni_code: str,
        name: str,
        email: str,
        roles: list[dict],
    ) -> SystemUser:
        user = self.get_by_uni_code(uni_code)

        if user is None:
            user = SystemUser(uni_code=uni_code, status="active")
            self.db.add(user)

        user.name = name
        user.email = email
        user.external_roles = roles
        user.last_login_at = datetime.now()

        self.db.commit()
        self.db.refresh(user)

        return user
