from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OnboardingAnswer(BaseModel):
    feature: str
    value: float = Field(ge=0, le=1)
    importance: float = Field(default=0.7, ge=0, le=1)
    scope: str = "global"


class OnboardingPayload(BaseModel):
    answers: list[OnboardingAnswer]


class FeedbackPayload(BaseModel):
    status: Literal["interested", "planned", "started", "paused", "completed", "abandoned", "rejected"]
    progress: float = Field(default=0, ge=0, le=100)
    enjoyment: float | None = Field(default=None, ge=0, le=100)
    quality: float | None = Field(default=None, ge=0, le=100)
    rewatch_value: float = Field(default=50, ge=0, le=100)
    aspects: dict[str, float] = Field(default_factory=dict)
    notes: str = ""
    reason: str | None = None


class RecommendationContext(BaseModel):
    mode: Literal["entertainment", "focus", "discovery", "comfort"] = "entertainment"
    media_types: list[str] = Field(default_factory=list)
    time_available: int | None = Field(default=None, ge=5)
    energy: Literal["low", "medium", "high"] = "medium"
    exploration: float = Field(default=0.35, ge=0, le=1)
    language: str | None = None
    dub_required: bool = False
    completed_only: bool = False
    limit: int = Field(default=8, ge=1, le=20)


class MediaCreatePayload(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    media_type: str = Field(min_length=1, max_length=32)
    description: str = Field(default="", max_length=4000)
    language: str = Field(default="English", max_length=64)
    status: str = Field(default="completed", max_length=32)
    runtime_minutes: int | None = Field(default=None, ge=1)
    commitment: str = Field(default="medium", max_length=64)
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    features: dict[str, float] = Field(default_factory=dict)
    downsides: list[str] = Field(default_factory=list)
    dub_available: bool = False
    hidden_gem: bool = False
    quality_prior: float = Field(default=0.7, ge=0, le=1)
