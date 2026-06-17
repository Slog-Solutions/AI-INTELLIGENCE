from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.session import SessionLocal
from ..models import User, Role
from ..schemas import UserOut, UserCreate
from ..services.user_service import UserService
from ..services.audit_service import AuditService
from ..core.dependencies import get_current_user
from ..core.rbac import require_roles

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_roles("Super Admin"))):
    users = db.query(User).all()
    return [
        UserOut(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            department_id=user.department_id,
            unit_id=user.unit_id,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        for user in users
    ]

@router.post("/create", response_model=UserOut)
def create_user(request: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles("Super Admin"))):
    role = db.query(Role).filter(Role.name == request.role).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = UserService.create_user(
        db,
        username=request.username,
        email=request.email,
        password=request.password,
        role=role,
        full_name=request.full_name,
        department_id=request.department_id,
        unit_id=request.unit_id,
    )
    AuditService.create_entry(db, current_user.id, "user_create", "users", f"Created user {user.username} with role {role.name}")
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role.name,
        department_id=user.department_id,
        unit_id=user.unit_id,
        is_active=user.is_active,
        created_at=user.created_at,
    )
