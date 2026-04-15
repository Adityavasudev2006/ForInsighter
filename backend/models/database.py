from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./docplatform.db")
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    questions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    view_manifest_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    doc_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    task_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    doc_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


@asynccontextmanager
async def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()


async def create_all() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight SQLite schema evolution for existing local databases.
        if DATABASE_URL.startswith("sqlite"):
            result = await conn.exec_driver_sql("PRAGMA table_info(documents)")
            columns = {row[1] for row in result.fetchall()}
            if "processing_error" not in columns:
                await conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN processing_error TEXT")
            if "profile_json" not in columns:
                await conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN profile_json TEXT")
            if "view_manifest_json" not in columns:
                await conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN view_manifest_json TEXT")
