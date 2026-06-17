from sqlalchemy.orm import Session
from ..models import AuditLog

class AuditService:
    @staticmethod
    def create_entry(db: Session, user_id: int | None, action: str, module: str, description: str):
        audit = AuditLog(user_id=user_id, action=action, module=module, description=description)
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
