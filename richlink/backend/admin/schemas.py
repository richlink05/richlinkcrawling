"""FastAPI Admin이 사용하는 요청/응답 Pydantic 스키마.

아키텍처 변경(2026-10): 승인/병합 개념은 사라졌다(실제 노출 승인은 홈해버
관리자 화면에서 함). 여기서는 "크롤링이 뭘 모았는지, 홈해버 전송이
성공했는지/실패했는지"를 확인하고, 실패한 건을 재시도시키는 용도로만 쓴다.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from backend.models.enums import SubmissionStatus


class ProjectOut(BaseModel):
    """Project 조회 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    address: str
    city: str
    district: str
    builder_name: str | None
    raw_type: str
    mapped_type: str | None
    raw_status: str | None
    mapped_status: str | None
    price_min: float | None
    price_max: float | None
    area_min: float | None
    area_max: float | None
    submission_status: SubmissionStatus
    submitted_at: datetime | None
    attempt_count: int
    homehaver_listing_id: str | None
    last_error: str | None
    supply_count: int | None
    move_in_date: date | None
    created_at: datetime
    updated_at: datetime


class RetrySummaryOut(BaseModel):
    """재시도 실행 결과 요약."""

    attempted: int
    success: int
    failed: int
