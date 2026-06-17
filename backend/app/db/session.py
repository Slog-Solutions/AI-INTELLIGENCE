from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from ..config import DATABASE_URL

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine, future=True)
