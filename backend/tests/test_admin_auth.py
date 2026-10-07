"""어드민 토큰 인증 테스트.

실제 ADMIN_TOKEN 설정 여부/일치 여부에 따라 어드민 API가 올바르게
막히는지(401/503) 확인한다. get_settings()는 lru_cache 싱글턴이라,
테스트마다 cache_clear()로 초기화해 환경변수 몽키패치가 반영되게 한다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.admin.router import get_admin_service
from backend.api.main import app
from backend.config.settings import get_settings


class _NoopAdminService:
    """인증 자체만 검증하면 되므로, DB 접근 없이 빈 값만 돌려준다."""

    async def list_projects(self, status=None, limit: int = 50, offset: int = 0) -> list:
        return []


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_admin_service] = lambda: _NoopAdminService()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


class TestAdminTokenMissing:
    def test_rejects_when_admin_token_not_configured(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setenv("ADMIN_TOKEN", "")
        get_settings.cache_clear()

        response = client.get("/admin/projects", headers={"X-Admin-Token": "anything"})

        assert response.status_code == 503


class TestAdminTokenMismatch:
    def test_rejects_wrong_token(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setenv("ADMIN_TOKEN", "correct-token")
        get_settings.cache_clear()

        response = client.get("/admin/projects", headers={"X-Admin-Token": "wrong-token"})

        assert response.status_code == 401

    def test_rejects_missing_header(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setenv("ADMIN_TOKEN", "correct-token")
        get_settings.cache_clear()

        response = client.get("/admin/projects")

        assert response.status_code == 401
