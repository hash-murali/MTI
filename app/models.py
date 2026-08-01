from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class MediaItem(Base):
    __tablename__ = "media_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(64), default="English")
    status: Mapped[str] = mapped_column(String(32), default="completed")
    runtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commitment: Mapped[str] = mapped_column(String(64), default="medium")
    popularity: Mapped[float] = mapped_column(Float, default=0.5)
    quality_prior: Mapped[float] = mapped_column(Float, default=0.7)
    hidden_gem: Mapped[bool] = mapped_column(Boolean, default=False)
    dub_available: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    features: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    downsides: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    consumption: Mapped["ConsumptionRecord | None"] = relationship(back_populates="media", uselist=False)
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="media")


class ConsumptionRecord(Base):
    __tablename__ = "consumption_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="interested")
    progress: Mapped[float] = mapped_column(Float, default=0)
    rewatch_count: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    media: Mapped[MediaItem] = relationship(back_populates="consumption")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), index=True)
    enjoyment: Mapped[float] = mapped_column(Float)
    quality: Mapped[float] = mapped_column(Float)
    rewatch_value: Mapped[float] = mapped_column(Float, default=0.5)
    aspects: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    media: Mapped[MediaItem] = relationship(back_populates="evaluations")


class PreferenceDimension(Base):
    __tablename__ = "preference_dimensions"
    __table_args__ = (UniqueConstraint("scope", "feature", name="uq_scope_feature"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), default="global")
    feature: Mapped[str] = mapped_column(String(64), index=True)
    preferred_value: Mapped[float] = mapped_column(Float, default=0.5)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.15)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    explicit: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InteractionEvent(Base):
    __tablename__ = "interaction_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media_items.id"), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
