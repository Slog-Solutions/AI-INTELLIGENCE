import os
import tempfile
from pathlib import Path

TEST_ROOT = Path(tempfile.mkdtemp(prefix="atip_phase1_"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(TEST_ROOT / 'test.db').as_posix()}")
os.environ.setdefault("UPLOAD_DIR", str(TEST_ROOT / "uploads"))
os.environ.setdefault("VECTOR_DIR", str(TEST_ROOT / "vector_store"))
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL", "qwen3")

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import create_password_hash
from backend.app.db.session import SessionLocal, engine
from backend.app.main import app
from backend.app.models import Base, Department, Role, Unit, User


ACCOUNTS = [
    ("admin", "admin@atip.example.com", "ATIP Super Admin", "Admin123!", "Super Admin"),
    ("co_alpha", "co_alpha@atip.example.com", "Alpha Commanding Officer", "CO123!", "Commanding Officer"),
    ("instructor_alpha", "instructor_alpha@atip.example.com", "Alpha Instructor", "Inst123!", "Instructor"),
    ("analyst_main", "analyst_main@atip.example.com", "Main Analyst", "Ana123!", "Analyst"),
]


def seed_test_data() -> None:
    with SessionLocal() as session:
        roles = {}
        for role_name in ["Super Admin", "Commanding Officer", "Instructor", "Analyst"]:
            role = Role(name=role_name, description=f"{role_name} role")
            session.add(role)
            session.flush()
            roles[role_name] = role

        department = Department(name="Training Command")
        session.add(department)
        session.flush()
        unit = Unit(name="Alpha Training Unit", department_id=department.id)
        session.add(unit)
        session.flush()

        for username, email, full_name, password, role_name in ACCOUNTS:
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


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_test_data()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    def _headers(username: str = "admin", password: str = "Admin123!") -> dict[str, str]:
        response = client.post("/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _headers
