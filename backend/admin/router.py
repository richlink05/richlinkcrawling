"""FastAPI Admin 라우터.

아키텍처 변경(2026-10): 승인/병합 엔드포인트는 제거했다(실제 노출 승인은
홈해버 관리자 화면에서 한다). 여기서는 수집 현황 확인, 삭제, 실패건
재시도만 제공한다.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.admin.auth import require_admin_token
from backend.admin.schemas import ProjectOut, RetrySummaryOut
from backend.models.base import get_db_session
from backend.models.enums import SubmissionStatus
from backend.services.admin_service import AdminService

router = APIRouter(
    prefix="/admin/projects", tags=["admin"], dependencies=[Depends(require_admin_token)]
)


def get_admin_service(session: AsyncSession = Depends(get_db_session)) -> AdminService:
    """AdminService를 FastAPI Depends로 의존성 주입한다."""
    return AdminService(session)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    submission_status: SubmissionStatus | None = Query(default=None),
    limit: int = 50,
    offset: int = 0,
    service: AdminService = Depends(get_admin_service),
) -> list[ProjectOut]:
    """수집 결과 목록을 조회한다. submission_status로 필터링할 수 있다."""
    projects = await service.list_projects(status=submission_status, limit=limit, offset=offset)
    return [ProjectOut.model_validate(project) for project in projects]


@router.get("/summary/counts")
async def summary_counts(service: AdminService = Depends(get_admin_service)) -> dict[str, int]:
    """상태별(pending/success/failed/skipped) 건수 요약. 화면 상단 카드용."""
    return await service.count_by_status()


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID, service: AdminService = Depends(get_admin_service)
) -> ProjectOut:
    """단건 조회."""
    project = await service.get_project(project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "프로젝트를 찾을 수 없습니다.")
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID, service: AdminService = Depends(get_admin_service)
) -> None:
    """잘못 수집된 현장을 수집함에서 삭제한다."""
    deleted = await service.delete_project(project_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "프로젝트를 찾을 수 없습니다.")


@router.post("/retry-failed", response_model=RetrySummaryOut)
async def retry_failed(service: AdminService = Depends(get_admin_service)) -> RetrySummaryOut:
    """전송 실패/대기 건들을 다시 홈해버로 전송 시도한다."""
    summary = await service.retry_failed()
    return RetrySummaryOut(**summary)
