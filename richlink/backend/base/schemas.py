"""Spider의 parse() 결과를 담는 Pydantic 스키마.

Spider는 ORM 모델을 직접 다루지 않고 이 스키마로만 결과를 반환한다.
type/status는 아직 크롤링 원본 표현 그대로(raw) 두고, 홈해버가 요구하는
값으로의 변환은 전송 직전(services/homehaver_payload.py)에 한다 — Spider는
사이트 구조만 신경 쓰고, 홈해버 API 규격은 몰라도 되게 하기 위함이다.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class UnitTypeData(BaseModel):
    """평형 타입 원본 데이터. 저장은 안 하고, Project.price_min/max·area_min/max를
    집계하는 데만 쓰고 버려진다 (홈해버는 평형별 상세가 아니라 범위만 필요해서)."""

    raw_type: str
    area_sqm: float | None = None
    price_text: str | None = None  # 예: "3억 5,000만원", "22.8억~25.3억"


class ImageData(BaseModel):
    """이미지 원본 URL 데이터. 다운로드하지 않고 URL을 그대로 홈해버에 전달한다."""

    source_url: str
    category_hint: str | None = None  # 예: "썸네일", "평면도" 등 사이트에서 유추 가능한 경우


class ProjectData(BaseModel):
    """Spider의 parse() 결과 단위. Project 테이블 저장 전 중간 표현."""

    title: str
    address: str
    city: str
    district: str
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None

    builder_name: str | None = None

    raw_type: str  # 예: "아파트", "생숙", "주상복합" — 사이트 원본 표현 그대로
    raw_status: str | None = None  # 예: "분양중", "분양완료" — 사이트 원본 표현 그대로

    supply_count: int | None = None
    move_in_date: date | None = None
    subscription_date: date | None = None
    model_house: str | None = None
    description: str | None = None

    unit_types: list[UnitTypeData] = Field(default_factory=list)
    images: list[ImageData] = Field(default_factory=list)

    source_url: str
    spider_name: str
