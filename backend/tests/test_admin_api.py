"""FastAPI Admin 라우터 HTTP 계층 검증 테스트.

실제 DB 대신 AdminService를 Fake 구현체로 의존성 오버라이드해 검증한다.
"""
from __future__ import annotations

import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.admin.auth import require_admin_token
from backend.admin.router import get_admin_service
from backend.api.main import app
from backend.models.enums import SubmissionStatus


class _FakeProject:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.title = "테스트 아파트"
        self.address = "서울특별시 강남구 테헤란로 1"
        self.city = "서울특별시"
        self.district = "강남구"
        self.builder_name = "롯데건설"
        self.raw_type = "아파트"
        self.mapped_type = "아파트"
        self.raw_status = "분양중"
        self.mapped_status = "분양중"
        self.price_min = 228_000.0
        self.price_max = 253_000.0
        self.area_min = 84.98
        self.area_max = 114.82
        self.submission_status = SubmissionStatus.PENDING
        self.submitted_at = None
        self.attempt_count = 0
        self.homehaver_listing_id = None
        self.last_error = None
        self.supply_count = None
        self.move_in_date = None
        now = datetime.datetime.now(datetime.timezone.utc)
        self.created_at = now
        self.updated_at = now


class _FakeAdminService:
    def __init__(self) -> None:
        self.project = _FakeProject()

    async def list_projects(self, status=None, limit: int = 50, offset: int = 0) -> list[_FakeProject]:
        return [self.project]

    async def get_project(self, project_id: uuid.UUID) -> _FakeProject | None:
        return self.project if project_id == self.project.id else None

    async def delete_project(self, project_id: uuid.UUID) -> bool:
        return project_id == self.project.id

    async def retry_failed(self) -> dict[str, int]:
        return {"attempted": 1, "success": 1, "failed": 0}

    async def count_by_status(self) -> dict[str, int]:
        return {"pending": 1, "success": 0, "failed": 0, "skipped": 0}


@pytest.fixture
def client() -> TestClient:
    fake_service = _FakeAdminService()
    app.dependency_overrides[get_admin_service] = lambda: fake_service
    # 인증 토큰 검사는 이 테스트의 관심사가 아니므로(별도 test_admin_auth.py에서
    # 검증) 항상 통과하도록 오버라이드한다.
    app.dependency_overrides[require_admin_token] = lambda: None
    with TestClient(app) as test_client:
        test_client.fake_service = fake_service  # type: ignore[attr-defined]
        yield test_client
    app.dependency_overrides.clear()


class TestListProjects:
    def test_returns_project_list(self, client: TestClient) -> None:
        response = client.get("/admin/projects")

        assert response.status_code == 200
        assert len(response.json()) == 1


class TestDeleteProject:
    def test_deletes_existing_project(self, client: TestClient) -> None:
        project_id = client.fake_service.project.id  # type: ignore[attr-defined]

        response = client.delete(f"/admin/projects/{project_id}")

        assert response.status_code == 204

    def test_returns_404_for_unknown_project(self, client: TestClient) -> None:
        response = client.delete(f"/admin/projects/{uuid.uuid4()}")

        assert response.status_code == 404


class TestRetryFailed:
    def test_returns_summary(self, client: TestClient) -> None:
        response = client.post("/admin/projects/retry-failed")

        assert response.status_code == 200
        assert response.json() == {"attempted": 1, "success": 1, "failed": 0}


class TestSummaryCounts:
    def test_returns_counts_by_status(self, client: TestClient) -> None:
        response = client.get("/admin/projects/summary/counts")

        assert response.status_code == 200
        assert response.json() == {"pending": 1, "success": 0, "failed": 0, "skipped": 0}
