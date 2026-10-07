"""initial schema - RichLink 수집함(staging) 테이블

RichLink 자신의 Supabase 프로젝트(홈해버 DB와는 별개)에 적용하는
마이그레이션이다. projects / project_images / project_sources 3개
테이블만 존재한다 — 홈해버로 전송하기 전까지 임시로 보관하는 용도라서
서비스 화면용 테이블(평형별 가격, 평면도 등)은 두지 않는다.

Revision ID: 0001
Revises:
Create Date: 2026-10-03

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

IMAGE_CATEGORY = postgresql.ENUM(
    "THUMBNAIL", "FLOOR_PLAN", "INFRA",
    name="image_category",
    create_type=False,  # 아래 upgrade()에서 명시적으로 미리 만들기 때문에, 테이블 생성 시 중복 생성 방지
)
SUBMISSION_STATUS = postgresql.ENUM(
    "PENDING", "SUCCESS", "FAILED", "SKIPPED",
    name="submission_status",
    create_type=False,  # 아래 upgrade()에서 명시적으로 미리 만들기 때문에, 테이블 생성 시 중복 생성 방지
)


def upgrade() -> None:
    bind = op.get_bind()
    IMAGE_CATEGORY.create(bind, checkfirst=True)
    SUBMISSION_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("address", sa.String(300), nullable=False),
        sa.Column("city", sa.String(50), nullable=False),
        sa.Column("district", sa.String(50), nullable=False),
        sa.Column("lat", sa.Float, nullable=True),
        sa.Column("lng", sa.Float, nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("builder_name", sa.String(200), nullable=True),
        sa.Column("raw_type", sa.String(50), nullable=False),
        sa.Column("mapped_type", sa.String(20), nullable=True),
        sa.Column("raw_status", sa.String(50), nullable=True),
        sa.Column("mapped_status", sa.String(20), nullable=True),
        sa.Column("price_min", sa.Float, nullable=True),
        sa.Column("price_max", sa.Float, nullable=True),
        sa.Column("area_min", sa.Float, nullable=True),
        sa.Column("area_max", sa.Float, nullable=True),
        sa.Column("supply_count", sa.Integer, nullable=True),
        sa.Column("move_in_date", sa.Date, nullable=True),
        sa.Column("subscription_date", sa.Date, nullable=True),
        sa.Column("model_house", sa.String(300), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column("submission_status", SUBMISSION_STATUS, nullable=False, server_default="PENDING"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("homehaver_listing_id", sa.String(100), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
    )
    op.create_index("ix_projects_city_district", "projects", ["city", "district"])
    op.create_index("ix_projects_submission_status", "projects", ["submission_status"])

    op.create_table(
        "project_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", IMAGE_CATEGORY, nullable=False, server_default="INFRA"),
        sa.Column("image_url", sa.String(500), nullable=False),
    )

    op.create_table(
        "project_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("spider_name", sa.String(100), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.UniqueConstraint("project_id", "source_url", name="uq_project_source_url"),
    )


def downgrade() -> None:
    op.drop_table("project_sources")
    op.drop_table("project_images")
    op.drop_index("ix_projects_submission_status", table_name="projects")
    op.drop_index("ix_projects_city_district", table_name="projects")
    op.drop_table("projects")

    bind = op.get_bind()
    SUBMISSION_STATUS.drop(bind, checkfirst=True)
    IMAGE_CATEGORY.drop(bind, checkfirst=True)
