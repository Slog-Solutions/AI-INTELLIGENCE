from sqlalchemy.orm import Session
from ..models import User, Role
from ..core.security import create_password_hash, verify_password

class UserService:
    @staticmethod
    def get_user_by_username(db: Session, username: str):
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def create_user(db: Session, username: str, email: str, password: str, role: Role, full_name: str | None = None, department_id: int | None = None, unit_id: int | None = None):
        hashed_password = create_password_hash(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role=role,
            full_name=full_name,
            department_id=department_id,
            unit_id=unit_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str):
        user = UserService.get_user_by_username(db, username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
