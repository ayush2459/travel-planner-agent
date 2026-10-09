"""Persistent trip storage. SQLite works locally; PostgreSQL is supported via DATABASE_URL."""
from __future__ import annotations
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, String, Text, DateTime, select, desc, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
raw_url = os.getenv("DATABASE_URL", "").strip()
if raw_url:
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    DATABASE_URL = raw_url
else:
    DATABASE_URL = f"sqlite:///{(ROOT / 'travel_planner.db').as_posix()}"

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(180), default="New trip")
    messages_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

class TripRevision(Base):
    __tablename__ = "trip_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_id: Mapped[str] = mapped_column(String(80), index=True)
    messages_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

Base.metadata.create_all(engine)

def _clean_messages(messages: list[dict]) -> list[dict]:
    clean = []
    for message in messages:
        role = message.get("role")
        if role not in ("user", "assistant"):
            continue
        item = {"role": role, "content": str(message.get("content", ""))}
        if role == "assistant":
            item["meta"] = message.get("meta", {})
        clean.append(item)
    return clean

def _safe_title(messages: list[dict]) -> str:
    for message in messages:
        if message.get("role") == "user":
            text = str(message.get("content", "")).strip().replace("\n", " ")
            if text:
                return text[:74] + ("…" if len(text) > 74 else "")
    return "New trip"

def save_trip(owner_id: str, trip_id: str, messages: list[dict]) -> None:
    now = datetime.now(timezone.utc)
    clean = _clean_messages(messages)
    payload = json.dumps(clean, ensure_ascii=False)
    with SessionLocal() as db:
        trip = db.get(Trip, trip_id)
        if trip and trip.owner_id != owner_id:
            raise PermissionError("This trip does not belong to the current workspace.")
        if not trip:
            trip = Trip(id=trip_id, owner_id=owner_id, title=_safe_title(clean), messages_json=payload, created_at=now, updated_at=now)
            db.add(trip)
        else:
            trip.messages_json = payload
            trip.title = _safe_title(clean)
            trip.updated_at = now
        latest = db.scalar(select(TripRevision).where(TripRevision.trip_id == trip_id, TripRevision.owner_id == owner_id).order_by(desc(TripRevision.created_at)).limit(1))
        if not latest or latest.messages_json != payload:
            db.add(TripRevision(id=str(uuid.uuid4()), trip_id=trip_id, owner_id=owner_id, messages_json=payload, created_at=now))
        db.commit()

def list_trips(owner_id: str, limit: int = 50) -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(select(Trip).where(Trip.owner_id == owner_id).order_by(desc(Trip.updated_at)).limit(limit)).all()
        return [{"id": r.id, "title": r.title, "created_at": r.created_at, "updated_at": r.updated_at, "message_count": len(json.loads(r.messages_json or "[]"))} for r in rows]

def load_trip(owner_id: str, trip_id: str) -> list[dict] | None:
    with SessionLocal() as db:
        row = db.get(Trip, trip_id)
        if not row or row.owner_id != owner_id:
            return None
        return json.loads(row.messages_json or "[]")

def list_revisions(owner_id: str, trip_id: str, limit: int = 20) -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(select(TripRevision).where(TripRevision.owner_id == owner_id, TripRevision.trip_id == trip_id).order_by(desc(TripRevision.created_at)).limit(limit)).all()
        return [{"id": r.id, "created_at": r.created_at, "message_count": len(json.loads(r.messages_json or "[]"))} for r in rows]

def load_revision(owner_id: str, trip_id: str, revision_id: str) -> list[dict] | None:
    with SessionLocal() as db:
        row = db.get(TripRevision, revision_id)
        if not row or row.owner_id != owner_id or row.trip_id != trip_id:
            return None
        return json.loads(row.messages_json or "[]")

def delete_trip(owner_id: str, trip_id: str) -> bool:
    with SessionLocal() as db:
        row = db.get(Trip, trip_id)
        if not row or row.owner_id != owner_id:
            return False
        db.execute(delete(TripRevision).where(TripRevision.owner_id == owner_id, TripRevision.trip_id == trip_id))
        db.delete(row)
        db.commit()
        return True

def storage_kind() -> str:
    return "PostgreSQL" if DATABASE_URL.startswith("postgresql") else "Local SQLite"
