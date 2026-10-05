"""Repository 패턴 구현.

DB 접근(쿼리) 로직을 서비스 레이어로부터 분리한다.
"""
from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import Base
from backend.models.enums import SubmissionStatus
from backend.models.project import Project

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """모든 Repository가 상속하는 공통 CRUD 베이스 클래스."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        """세션을 주입받는다 (의존성 주입)."""
        self._session = session

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelT | None:
        """기본키로 단건 조회한다."""
        return await self._session.get(self.model, entity_id)

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        """페이징 처리된 전체 목록을 조회한다."""
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, entity: ModelT) -> ModelT:
        """신규 엔티티를 세션에 추가하고 flush한다."""
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        """엔티티를 삭제한다."""
        await self._session.delete(entity)
        await self._session.flush()


class ProjectRepository(BaseRepository[Project]):
    """Project 전용 조회/저장 로직."""

    model = Project

    async def find_by_source_url(self, source_url: str) -> Project | None:
        """정확히 같은 원본 URL에서 이미 수집한 적 있는 Project를 조회한다.

        같은 사이트를 반복 크롤링했을 때 중복 저장을 막는 1차 필터로 쓴다.
        """
        from backend.models.project import ProjectSource

        stmt = (
            select(Project)
            .join(ProjectSource, ProjectSource.project_id == Project.id)
            .where(ProjectSource.source_url == source_url)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def find_candidates_for_dedup(self, city: str, district: str) -> list[Project]:
        """동일 시/구 내 후보 목록을 조회한다.

        DuplicateDetectionService가 이 목록을 대상으로 이름/주소/좌표/전화번호
        유사도를 계산해 90% 이상이면 "이미 수집된 현장"으로 판단한다.
        """
        stmt = select(Project).where(Project.city == city, Project.district == district)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_submission_status(
        self, status: SubmissionStatus, limit: int = 200
    ) -> list[Project]:
        """특정 전송 상태(예: FAILED)인 건들을 조회한다. 재시도 대상 선별에 쓴다."""
        stmt = select(Project).where(Project.submission_status == status).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
