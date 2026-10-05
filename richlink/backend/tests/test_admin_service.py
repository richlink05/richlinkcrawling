"""AdminService(조회/삭제/재시도) 검증 테스트.

아키텍처 변경(2026-10): 승인/병합 기능은 제거했다 (실제 노출 승인은
홈해버 관리자 화면에서 한다).
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from backend.models.project import Project
from backend.services.admin_service import AdminService


def _make_project(**overrides: object) -> Project:
    base: dict[str, object] = dict(
        id=uuid.uuid4(), title="테스트", address="주소", city="서울특별시",
        district="강남구", raw_type="아파트",
    )
    base.update(overrides)
    return Project(**base)


class TestDeleteProject:
    async def test_deletes_existing_project(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = AsyncMock()
        service = AdminService(session)
        project = _make_project()
        monkeypatch.setattr(service._repository, "get_by_id", AsyncMock(return_value=project))
        delete_mock = AsyncMock()
        monkeypatch.setattr(service._repository, "delete", delete_mock)

        result = await service.delete_project(project.id)

        assert result is True
        delete_mock.assert_awaited_once_with(project)

    async def test_returns_false_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = AsyncMock()
        service = AdminService(session)
        monkeypatch.setattr(service._repository, "get_by_id", AsyncMock(return_value=None))

        result = await service.delete_project(uuid.uuid4())

        assert result is False


class TestRetryFailed:
    async def test_delegates_to_submission_service(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = AsyncMock()
        service = AdminService(session)

        from backend.services import admin_service as admin_service_module

        fake_summary = {"attempted": 2, "success": 1, "failed": 1}
        submit_pending_mock = AsyncMock(return_value=fake_summary)

        class _FakeSubmissionService:
            def __init__(self, session: object) -> None:
                pass

            submit_pending = submit_pending_mock

        monkeypatch.setattr(admin_service_module, "SubmissionService", _FakeSubmissionService)

        result = await service.retry_failed()

        assert result == fake_summary
        submit_pending_mock.assert_awaited_once()
