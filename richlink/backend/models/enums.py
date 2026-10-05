"""Project 관련 Enum 정의.

이 값들은 전부 홈해버 API(POST /api/crawler/listings)가 "정확히 이 문자열이
아니면 insert 자체를 거부"한다고 명시한 값이다. 크롤링 원본 사이트는 "생숙",
"주상복합", "분양완료" 같은 다른 표현을 쓰므로, 실제 전송 직전에
utils/type_mapper.py가 이 값들로 변환한다. 변환에 실패하면 전송하지 않고
SubmissionStatus.SKIPPED로 남긴다.
"""
from __future__ import annotations

import enum


class PropertyType(str, enum.Enum):
    """분양 상품 유형 — 홈해버가 허용하는 5개 값 중 정확히 하나."""

    APARTMENT = "아파트"
    OFFICETEL = "오피스텔"
    LIVING_ACCOMMODATION = "생활형숙박시설"
    KNOWLEDGE_INDUSTRY_CENTER = "지식산업센터"
    COMMERCIAL = "상가"


class ListingStatus(str, enum.Enum):
    """분양 진행 상태 — 홈해버가 허용하는 3개 값 중 하나. 안 보내면 서버 기본값(분양예정)."""

    UPCOMING = "분양예정"
    ONGOING = "분양중"
    CLOSED = "마감"


class ImageCategory(str, enum.Enum):
    """이미지 분류 — 홈해버 listing_images.category가 허용하는 3개 값."""

    THUMBNAIL = "썸네일"
    FLOOR_PLAN = "평면도"
    INFRA = "인프라"


class SubmissionStatus(str, enum.Enum):
    """홈해버 API로의 전송 상태. RichLink 자신의 수집함 DB에서만 쓰는 내부 상태다."""

    PENDING = "pending"  # 아직 전송 시도 안 함
    SUCCESS = "success"  # 전송 성공 (재전송 안 함)
    FAILED = "failed"  # 전송 실패 (다음 주기에 재시도)
    SKIPPED = "skipped"  # type/status를 홈해버 값으로 매핑할 수 없어 전송 자체를 안 함
