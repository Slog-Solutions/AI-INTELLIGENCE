import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import DATABASE_URL
from app.core.security import create_password_hash
from app.models import Base, Department, Role, Unit, User

engine = create_engine(DATABASE_URL, future=True)
Base.metadata.create_all(bind=engine)


def get_or_create_role(session: Session, name: str) -> Role:
    role = session.query(Role).filter(Role.name == name).first()
    if role:
        return role
    role = Role(name=name, description=f"{name} role")
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


def seed() -> None:
    with Session(engine) as session:
        roles = {
            name: get_or_create_role(session, name)
            for name in ["Super Admin", "Commanding Officer", "Instructor", "Analyst"]
        }

        department = session.query(Department).filter(Department.name == "Training Command").first()
        if not department:
            department = Department(name="Training Command")
            session.add(department)
            session.commit()
            session.refresh(department)

        unit = session.query(Unit).filter(Unit.name == "Alpha Training Unit").first()
        if not unit:
            unit = Unit(name="Alpha Training Unit", department_id=department.id)
            session.add(unit)
            session.commit()
            session.refresh(unit)

        accounts = [
            ("admin", "admin@atip.example.com", "ATIP Super Admin", "Admin123!", "Super Admin"),
            ("co_alpha", "co_alpha@atip.example.com", "Alpha Commanding Officer", "CO123!", "Commanding Officer"),
            ("instructor_alpha", "instructor_alpha@atip.example.com", "Alpha Instructor", "Inst123!", "Instructor"),
            ("analyst_main", "analyst_main@atip.example.com", "Main Analyst", "Ana123!", "Analyst"),
        ]

        for username, email, full_name, password, role_name in accounts:
            if session.query(User).filter(User.username == username).first():
                print(f"User already exists: {username}")
                continue
            session.add(
                User(
                    username=username,
                    email=email,
                    full_name=full_name,
                    hashed_password=create_password_hash(password),
                    role_id=roles[role_name].id,
                    department_id=department.id,
                    unit_id=unit.id,
                    is_active=True,
                )
            )
            session.commit()
            print(f"Created user: {username}")


if __name__ == "__main__":
    seed()
