"""FastAPI Admin이 사용하는 비즈니스 로직.

아키텍처 변경(2026-10): 승인/병합 기능은 제거했다. 이제 할 일은 수집
현황을 조회하고, 전송 실패 건을 삭제하거나 재시도시키는 것뿐이다.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.enums import SubmissionStatus
from backend.models.project import Project
from backend.models.repository import ProjectRepository
from backend.services.submission_service import SubmissionService
from backend.utils.logger import get_logger

logger = get_logger("admin_service")


class AdminService:
    """FastAPI Admin 라우터가 위임하는 관리 기능 구현체."""

    def __init__(self, session: AsyncSession) -> None:
        """세션을 주입받는다."""
        self._session = session
        self._repository = ProjectRepository(session)

    async def list_projects(
        self, status: SubmissionStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Project]:
        """수집 결과 목록을 조회한다. status로 필터링할 수 있다."""
        if status is not None:
            return await self._repository.list_by_submission_status(status, limit=limit)
        return await self._repository.list_all(limit=limit, offset=offset)

    async def get_project(self, project_id: uuid.UUID) -> Project | None:
        """단건 조회."""
        return await self._repository.get_by_id(project_id)

    async def delete_project(self, project_id: uuid.UUID) -> bool:
        """잘못 수집된 현장을 수집함에서 삭제한다 (홈해버에는 영향 없음)."""
        project = await self._repository.get_by_id(project_id)
        if project is None:
            return False
        await self._repository.delete(project)
        logger.success(f"수집함에서 삭제: {project.title}")
        return True

    async def retry_failed(self) -> dict[str, int]:
        """전송 실패/대기 건들을 다시 홈해버로 전송 시도한다."""
        service = SubmissionService(self._session)
        return await service.submit_pending()
