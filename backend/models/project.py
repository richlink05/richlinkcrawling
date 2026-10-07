"""Project 및 연관 엔티티 ORM 모델.

아키텍처 변경(2026-10): 이 DB는 홈해버 DB가 아니라 RichLink 자신의
"수집함(staging)" DB다. 역할이 완전히 바뀌었다:
  - 예전: 크롤링 결과를 여기(Project)에 "서비스용으로" 영구 저장
  - 지금: 크롤링 결과를 여기에 "임시로" 저장해서 ① 같은 현장을 중복으로 또
    보내지 않기 위한 비교 기준으로 쓰고 ② 홈해버 API 전송 성공/실패 여부를
    기록해 실패한 건 다음 주기에 재시도하기 위한 용도로만 쓴다.

그래서 평형별 가격 테이블(ProjectUnitType), 평면도 전용 테이블(FloorPlan),
승인 플래그(is_approved) 등 "서비스 화면에 보여주기 위한" 구조는 모두
제거했다. 평형별 가격/면적은 파싱 시점에 최소/최대로 집계해
price_min/price_max/area_min/area_max 컬럼에만 남긴다 (홈해버 API가
요구하는 형태가 그것뿐이라서).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import ImageCategory, SubmissionStatus
from backend.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """크롤링으로 수집한 분양현장 1건. RichLink 자신의 수집함에만 존재한다."""

    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_city_district", "city", "district"),
        Index("ix_projects_submission_status", "submission_status"),
    )

    # --- 원본 크롤링 데이터 (중복 비교 + 홈해버 전송용) ---
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    district: Mapped[str] = mapped_column(String(50), nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    builder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 크롤링 원본 표현 그대로("주상복합", "생숙" 등) + 홈해버 값으로 매핑한 결과
    raw_type: Mapped[str] = mapped_column(String(50), nullable=False)
    mapped_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mapped_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)  # 단위: 만원
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)  # 단위: 만원
    area_min: Mapped[float | None] = mapped_column(Float, nullable=True)  # 단위: ㎡
    area_max: Mapped[float | None] = mapped_column(Float, nullable=True)  # 단위: ㎡

    supply_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    move_in_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subscription_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    model_house: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- 홈해버 API 전송 상태 추적 ---
    submission_status: Mapped[SubmissionStatus] = mapped_column(
        SAEnum(SubmissionStatus, name="submission_status", native_enum=True),
        nullable=False,
        default=SubmissionStatus.PENDING,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    homehaver_listing_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    images: Mapped[list["ProjectImage"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    sources: Mapped[list["ProjectSource"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectImage(UUIDPrimaryKeyMixin, Base):
    """홈해버로 그대로 전달할 이미지 URL. 파일을 내려받지 않고 URL만 전달한다."""

    __tablename__ = "project_images"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[ImageCategory] = mapped_column(
        SAEnum(ImageCategory, name="image_category", native_enum=True),
        nullable=False,
        default=ImageCategory.INFRA,
    )
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="images")


class ProjectSource(UUIDPrimaryKeyMixin, Base):
    """이 프로젝트를 수집한 출처(사이트) 기록.

    같은 페이지를 반복 크롤링했을 때 재전송 여부를 판단하는 데 쓰고,
    같은 현장이 여러 사이트에서 발견된 경우의 증빙으로도 남는다.
    """

    __tablename__ = "project_sources"
    __table_args__ = (
        UniqueConstraint("project_id", "source_url", name="uq_project_source_url"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    spider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="sources")
