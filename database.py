import os
import enum
import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float, DateTime, Enum
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./store.db")

# Render يعطي رابط postgres:// القديم، وSQLAlchemy 2.x يحتاج postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class OrderStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), index=True, nullable=False)
    username = Column(String(128), nullable=True)
    full_name = Column(String(256), nullable=True)
    products_json = Column(Text, nullable=False)      # JSON نصي بأسماء المنتجات وكمياتها
    total = Column(Float, nullable=False)
    receipt_file_id = Column(String(256), nullable=False)  # file_id من تيليغرام (لا نخزن الصورة نفسها)
    status = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)
    admin_message_id = Column(Integer, nullable=True)  # لتعديل رسالة الأدمن لاحقاً
    admin_chat_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
