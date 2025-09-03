from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from database import Base, engine
from datetime import datetime

# Try to use pgvector when on Postgres
try:
    from pgvector.sqlalchemy import Vector
    USING_PGVECTOR = engine.url.get_backend_name().startswith("postgresql")
except Exception:
    Vector = None
    USING_PGVECTOR = False

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, nullable=False)
    receiver_id = Column(Integer, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Use pgvector(384) when Postgres is enabled; otherwise JSON fallback
    embedding = Column(Vector(384), nullable=True) if USING_PGVECTOR and Vector else Column(JSON, nullable=True)
