from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv, find_dotenv

# Load .env only when DATABASE_URL is not already set (local dev)
if not os.getenv("DATABASE_URL"):
    load_dotenv(find_dotenv())  # project .env if present
    # DO NOT force-load backend/.env in production images

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./rebellion_chat.db").strip()

# Normalize Postgres URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg2" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
