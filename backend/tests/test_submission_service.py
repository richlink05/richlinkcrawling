"""SubmissionService의 수집/중복판단/전송 오케스트레이션 검증 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.base.schemas import ProjectData
from backend.models.enums import SubmissionStatus
from backend.models.project import Project
from backend.services.homehaver_client import SubmissionResult
from backend.services.submission_service import SubmissionService


def _make_item(**overrides: object) -> ProjectData:
    base: dict[str, object] = dict(
        title="힐스테이트 강남", address="서울특별시 강남구 테헤란로 1",
        city="서울특별시", district="강남구", raw_type="아파트",
        source_url="https://example.com/1", spider_name="lotte",
    )
    base.update(overrides)
    return ProjectData(**base)


class _FakeClient:
    def __init__(self, results: list[SubmissionResult]) -> None:
        self._results = results
        self.received_payloads: list[dict] | None = None

    async def submit_batch(self, payloads: list[dict]) -> list[SubmissionResult]:
        self.received_payloads = payloads
        return self._results


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


class TestIngest:
    async def test_creates_new_project_when_nothing_matches(
        self, session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = SubmissionService(session, api_client=_FakeClient([]))
        monkeypatch.setattr(service._repository, "find_by_source_url", AsyncMock(return_value=None))
        monkeypatch.setattr(service._dedup, "find_existing", AsyncMock(return_value=None))
        add_mock = AsyncMock(side_effect=lambda project: project)
        monkeypatch.setattr(service._repository, "add", add_mock)

        await service.ingest([_make_item()])

        add_mock.assert_awaited_once()
        created: Project = add_mock.call_args.args[0]
        assert created.title == "힐스테이트 강남"
        assert created.submission_status == SubmissionStatus.PENDING

    async def test_skips_when_exact_source_already_known(
        self, session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = SubmissionService(session, api_client=_FakeClient([]))
        existing = Project(
            title="힐스테이트 강남", address="주소", city="서울특별시", district="강남구",
            raw_type="아파트",
        )
        monkeypatch.setattr(service._repository, "find_by_source_url", AsyncMock(return_value=existing))
        add_mock = AsyncMock()
        monkeypatch.setattr(service._repository, "add", add_mock)

        await service.ingest([_make_item()])

        add_mock.assert_not_called()

    async def test_marks_unmappable_type_as_skipped(
        self, session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = SubmissionService(session, api_client=_FakeClient([]))
        monkeypatch.setattr(service._repository, "find_by_source_url", AsyncMock(return_value=None))
        monkeypatch.setattr(service._dedup, "find_existing", AsyncMock(return_value=None))
        add_mock = AsyncMock(side_effect=lambda project: project)
        monkeypatch.setattr(service._repository, "add", add_mock)

        await service.ingest([_make_item(raw_type="듣도보도못한유형")])

        created: Project = add_mock.call_args.args[0]
        assert created.submission_status == SubmissionStatus.SKIPPED
        assert created.last_error is not None

    async def test_attaches_source_when_duplicate_found_from_other_site(
        self, session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = SubmissionService(session, api_client=_FakeClient([]))
        existing = Project(
            title="힐스테이트 강남", address="주소", city="서울특별시", district="강남구",
            raw_type="아파트",
        )
        monkeypatch.setattr(service._repository, "find_by_source_url", AsyncMock(return_value=None))
        monkeypatch.setattr(service._dedup, "find_existing", AsyncMock(return_value=existing))
        add_mock = AsyncMock()
        monkeypatch.setattr(service._repository, "add", add_mock)

        await service.ingest([_make_item(source_url="https://news.example.com/other")])

        add_mock.assert_not_called()
        assert len(existing.sources) == 1
        assert existing.sources[0].source_url == "https://news.example.com/other"


class TestSubmitPending:
    async def test_returns_zero_summary_when_nothing_to_send(
        self, session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = _FakeClient([])
        service = SubmissionService(session, api_client=client)
        monkeypatch.setattr(service._repository, "list_by_submission_status", AsyncMock(return_value=[]))

        summary = await service.submit_pending()

        assert summary == {"attempted": 0, "success": 0, "failed": 0}
        assert client.received_payloads is None

    async def test_updates_project_status_from_api_results(
        self, session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pending_project = Project(
            title="신규 현장", address="주소", city="서울특별시", district="강남구",
            raw_type="아파트", mapped_type="아파트", attempt_count=0,
        )
        client = _FakeClient(
            [SubmissionResult(client_ref=str(pending_project.id), success=True, listing_id="L1")]
        )
        service = SubmissionService(session, api_client=client)

        async def fake_list_by_status(status, limit=200):
            return [pending_project] if status == SubmissionStatus.PENDING else []

        monkeypatch.setattr(service._repository, "list_by_submission_status", fake_list_by_status)

        summary = await service.submit_pending()

        assert summary == {"attempted": 1, "success": 1, "failed": 0}
        assert pending_project.submission_status == SubmissionStatus.SUCCESS
        assert pending_project.homehaver_listing_id == "L1"
