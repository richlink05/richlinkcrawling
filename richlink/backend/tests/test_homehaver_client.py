"""HomehaverApiClient가 계약대로 요청/응답을 처리하는지 검증하는 테스트.

실제 네트워크 호출 없이 httpx.AsyncClient.post를 monkeypatch로 대체한다.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.config.settings import Settings
from backend.services.homehaver_client import HomehaverApiClient


def _settings(**overrides: object) -> Settings:
    base = dict(homehaver_api_token="test-token", homehaver_api_batch_size=2)
    base.update(overrides)
    return Settings(**base)


def _mock_response(status_code: int, json_body: dict) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_body
    response.text = str(json_body)
    return response


class TestSubmitBatch:
    async def test_returns_empty_list_for_empty_input(self) -> None:
        client = HomehaverApiClient(settings=_settings())

        results = await client.submit_batch([])

        assert results == []

    async def test_parses_successful_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = HomehaverApiClient(settings=_settings())
        response_body = {
            "ok": True, "total": 1, "inserted": 1, "failed": 0,
            "results": [{"client_ref": "abc", "success": True, "listing_id": "L1"}],
        }
        mock_post = AsyncMock(return_value=_mock_response(200, response_body))
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        monkeypatch.setattr(httpx.AsyncClient, "__aenter__", AsyncMock(return_value=httpx.AsyncClient()))
        monkeypatch.setattr(httpx.AsyncClient, "__aexit__", AsyncMock(return_value=None))

        results = await client.submit_batch([{"client_ref": "abc", "title": "t"}])

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].listing_id == "L1"

    async def test_401_marks_all_items_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = HomehaverApiClient(settings=_settings())
        mock_post = AsyncMock(return_value=_mock_response(401, {"ok": False, "error": "Unauthorized"}))
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        monkeypatch.setattr(httpx.AsyncClient, "__aenter__", AsyncMock(return_value=httpx.AsyncClient()))
        monkeypatch.setattr(httpx.AsyncClient, "__aexit__", AsyncMock(return_value=None))

        results = await client.submit_batch([{"client_ref": "abc", "title": "t"}])

        assert len(results) == 1
        assert results[0].success is False
        assert "인증" in results[0].error

    async def test_network_error_marks_items_failed_without_raising(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = HomehaverApiClient(settings=_settings())
        mock_post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        monkeypatch.setattr(httpx.AsyncClient, "__aenter__", AsyncMock(return_value=httpx.AsyncClient()))
        monkeypatch.setattr(httpx.AsyncClient, "__aexit__", AsyncMock(return_value=None))

        results = await client.submit_batch([{"client_ref": "abc", "title": "t"}])

        assert results[0].success is False

    async def test_splits_into_chunks_of_batch_size(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = HomehaverApiClient(settings=_settings(homehaver_api_batch_size=1))
        response_body = {
            "ok": True, "total": 1, "inserted": 1, "failed": 0,
            "results": [{"client_ref": "x", "success": True, "listing_id": "L"}],
        }
        mock_post = AsyncMock(return_value=_mock_response(200, response_body))
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        monkeypatch.setattr(httpx.AsyncClient, "__aenter__", AsyncMock(return_value=httpx.AsyncClient()))
        monkeypatch.setattr(httpx.AsyncClient, "__aexit__", AsyncMock(return_value=None))

        await client.submit_batch(
            [{"client_ref": "1", "title": "a"}, {"client_ref": "2", "title": "b"}]
        )

        assert mock_post.call_count == 2
