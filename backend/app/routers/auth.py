from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..schemas import LoginRequest, LoginResponse, TokenResponse, UserOut, UserCreate
from ..db.session import SessionLocal
from ..services.user_service import UserService
from ..services.audit_service import AuditService
from ..core.security import create_access_token
from ..models import Role
from ..core.dependencies import get_current_user

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = UserService.authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(subject=str(user.id))
    AuditService.create_entry(db, user.id, "login", "auth", f"User {user.username} logged in")
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            department_id=user.department_id,
            unit_id=user.unit_id,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(current_user=Depends(get_current_user)):
    token = create_access_token(subject=str(current_user.id))
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut)
def get_profile(current_user=Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.name,
        department_id=current_user.department_id,
        unit_id=current_user.unit_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )

@router.post("/register", response_model=UserOut)
def register(request: UserCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role.name != "Super Admin":
        raise HTTPException(status_code=403, detail="Only Super Admin may create accounts")
    role = db.query(Role).filter(Role.name == request.role).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = UserService.create_user(db, request.username, request.email, request.password, role, request.full_name, request.department_id, request.unit_id)
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
