from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CarouselStatus(str, Enum):
    PENDING = "pending"
    ANALYSING = "analysing"
    QUESTIONING = "questioning"
    BRIEFING = "briefing"
    BUILDING = "building"
    DONE = "done"
    FAILED = "failed"


class BrandAnalysis(BaseModel):
    palette: list[str]  # hex values
    tone: str
    visual_style: str
    typography_feel: str


class StyleAnalysis(BaseModel):
    layout_pattern: str
    slide_structure: str
    design_density: str


class CarouselJob(BaseModel):
    id: str
    slack_user_id: str
    slack_thread_ts: str
    slack_channel_id: str
    topic: str
    brand_analysis: BrandAnalysis | None = None
    style_analysis: StyleAnalysis | None = None
    questions_asked: list[str] = Field(default_factory=list)
    user_answers: str | None = None
    brief: dict[str, Any] | None = None
    canva_url: str | None = None
    status: CarouselStatus = CarouselStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
