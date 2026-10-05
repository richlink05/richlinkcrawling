"""DuplicateDetectionService의 유사도 계산 및 조회 로직 검증 테스트.

아키텍처 변경(2026-10): merge()는 제거했다(서로 다른 Project를 합칠 필요가
없어짐). find_existing()이 "RichLink 자신의 수집함 안에서 이미 아는
현장인지"만 판단한다.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.base.schemas import ProjectData
from backend.models.project import Project
from backend.services.duplicate_service import DuplicateDetectionService


def _make_candidate(**overrides: object) -> ProjectData:
    base: dict[str, object] = dict(
        title="힐스테이트 강남",
        address="서울특별시 강남구 테헤란로 123",
        city="서울특별시",
        district="강남구",
        lat=37.5012,
        lng=127.0396,
        phone="02-1234-5678",
        raw_type="아파트",
        source_url="https://example.com/1",
        spider_name="lotte",
    )
    base.update(overrides)
    return ProjectData(**base)


def _make_existing(**overrides: object) -> Project:
    base: dict[str, object] = dict(
        title="힐스테이트 강남", address="서울특별시 강남구 테헤란로 123",
        city="서울특별시", district="강남구", lat=37.5012, lng=127.0396,
        phone="02-1234-5678", raw_type="아파트",
    )
    base.update(overrides)
    return Project(**base)


class TestComputeSimilarity:
    def test_identical_project_scores_near_one(self) -> None:
        score = DuplicateDetectionService.compute_similarity(_make_candidate(), _make_existing())
        assert score >= 0.90

    def test_completely_different_project_scores_low(self) -> None:
        candidate = _make_candidate(
            title="자이 부산", address="부산광역시 해운대구 센텀로 1",
            phone="051-000-0000", lat=35.1631, lng=129.1300,
        )
        existing = _make_existing()

        score = DuplicateDetectionService.compute_similarity(candidate, existing)

        assert score < 0.5

    def test_missing_coordinates_do_not_crash_and_score_zero_for_coordinates(self) -> None:
        candidate = _make_candidate(lat=None, lng=None)
        existing = _make_existing(lat=None, lng=None)

        score = DuplicateDetectionService.compute_similarity(candidate, existing)

        assert 0.0 <= score <= 1.0


class TestFindExisting:
    async def test_returns_best_match_above_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = DuplicateDetectionService(session=AsyncMock())
        existing = _make_existing()
        monkeypatch.setattr(
            service._repository, "find_candidates_for_dedup", AsyncMock(return_value=[existing])
        )

        result = await service.find_existing(_make_candidate())

        assert result is existing

    async def test_returns_none_when_below_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = DuplicateDetectionService(session=AsyncMock())
        different = _make_existing(title="전혀 다른 현장", address="부산광역시 해운대구 1", phone=None)
        monkeypatch.setattr(
            service._repository, "find_candidates_for_dedup", AsyncMock(return_value=[different])
        )

        result = await service.find_existing(_make_candidate())

        assert result is None
