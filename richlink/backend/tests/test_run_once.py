"""run_once_async()가 수집 → 저장 → 전송 순서로 호출하는지 검증한다."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.scheduler import run_once as run_once_module


class _FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class TestRunOnceAsync:
    async def test_calls_collect_ingest_and_submit_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        call_order: list[str] = []

        async def fake_collect_all() -> list[object]:
            call_order.append("collect")
            return []

        fake_session = _FakeSession()
        monkeypatch.setattr(run_once_module, "collect_all", fake_collect_all)
        monkeypatch.setattr(run_once_module, "AsyncSessionLocal", lambda: fake_session)

        ingest_mock = AsyncMock(side_effect=lambda items: call_order.append("ingest"))
        submit_mock = AsyncMock(
            side_effect=lambda: call_order.append("submit") or {"attempted": 0, "success": 0, "failed": 0}
        )

        class _FakeService:
            def __init__(self, session: object) -> None:
                pass

            ingest = ingest_mock
            submit_pending = submit_mock

        monkeypatch.setattr(run_once_module, "SubmissionService", _FakeService)

        await run_once_module.run_once_async()

        assert call_order == ["collect", "ingest", "submit"]
