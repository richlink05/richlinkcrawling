"""중복 판단 서비스.

아키텍처 변경(2026-10): 이제 홈해버 DB와는 비교하지 않는다(API로만 전달하고,
중복이면 홈해버 관리자가 승인 단계에서 직접 거절하는 구조로 역할을 나눴음).
여기서는 RichLink 자신의 수집함(staging) DB 안에서만 "이미 수집한 현장인지"를
판단한다 — 주소/현장명/좌표/전화번호를 종합한 가중 유사도가 90% 이상이면
같은 현장으로 본다.

과거 버전에 있던 merge()(여러 출처를 하나로 합치는 기능)는 제거했다. 이제
중복이면 그냥 "전송 안 함" 또는 "실패했으면 재시도"만 하면 되고, 데이터를
합칠 필요가 없기 때문이다 (서비스 화면 노출용 데이터가 아니라 전송 여부
판단용 데이터라서).
"""
from __future__ import annotations

import math

from rapidfuzz import fuzz
from sqlalchemy.ext.asyncio import AsyncSession

from backend.base.schemas import ProjectData
from backend.config.settings import Settings, get_settings
from backend.models.project import Project
from backend.models.repository import ProjectRepository
from backend.utils.logger import get_logger

logger = get_logger("duplicate_service")

# 각 신호에 부여하는 가중치. 합은 1.0.
_NAME_WEIGHT = 0.35
_ADDRESS_WEIGHT = 0.35
_COORDINATE_WEIGHT = 0.20
_PHONE_WEIGHT = 0.10

_COORDINATE_MATCH_RADIUS_METERS = 100.0
_EARTH_RADIUS_METERS = 6_371_000.0


class DuplicateDetectionService:
    """주소/현장명/좌표/전화번호 유사도를 종합해 "이미 수집된 현장인지" 판단한다."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        """세션과 설정을 주입받는다."""
        self._session = session
        self._repository = ProjectRepository(session)
        self._settings = settings or get_settings()

    async def find_existing(self, candidate: ProjectData) -> Project | None:
        """같은 시/구 내 기존 Project 중 유사도 임계값 이상인 항목을 찾는다."""
        existing_projects = await self._repository.find_candidates_for_dedup(
            candidate.city, candidate.district
        )
        best_match: Project | None = None
        best_score = 0.0

        for existing in existing_projects:
            score = self.compute_similarity(candidate, existing)
            if score > best_score:
                best_score = score
                best_match = existing

        if best_match is not None and best_score >= self._settings.duplicate_similarity_threshold:
            logger.info(f"중복(이미 수집됨) 판정: {candidate.title} ~= {best_match.title} (유사도 {best_score:.2f})")
            return best_match
        return None

    @staticmethod
    def compute_similarity(candidate: ProjectData, existing: Project) -> float:
        """가중 평균 유사도(0.0~1.0)를 계산한다."""
        name_score = fuzz.token_sort_ratio(candidate.title, existing.title) / 100
        address_score = fuzz.token_sort_ratio(candidate.address, existing.address) / 100
        coordinate_score = DuplicateDetectionService._coordinate_score(
            candidate.lat, candidate.lng, existing.lat, existing.lng
        )
        phone_score = 1.0 if (candidate.phone and candidate.phone == existing.phone) else 0.0

        return (
            name_score * _NAME_WEIGHT
            + address_score * _ADDRESS_WEIGHT
            + coordinate_score * _COORDINATE_WEIGHT
            + phone_score * _PHONE_WEIGHT
        )

    @staticmethod
    def _coordinate_score(
        lat1: float | None, lng1: float | None, lat2: float | None, lng2: float | None
    ) -> float:
        """반경 100m 이내면 1.0, 1km 밖이면 0.0, 그 사이는 선형 감소."""
        if lat1 is None or lng1 is None or lat2 is None or lng2 is None:
            return 0.0
        distance = _haversine_distance_meters(lat1, lng1, lat2, lng2)
        if distance <= _COORDINATE_MATCH_RADIUS_METERS:
            return 1.0
        max_distance = _COORDINATE_MATCH_RADIUS_METERS * 10
        return max(0.0, 1.0 - (distance - _COORDINATE_MATCH_RADIUS_METERS) / max_distance)


def _haversine_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 위경도 좌표 사이의 거리를 하버사인 공식으로 계산한다 (단위: 미터)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_METERS * c
