from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class PipelineRun(BaseModel):
    id: str
    carousel_job_id: str
    module: str
    status: str  # running, done, failed
    error: str | None = None
    duration_ms: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
