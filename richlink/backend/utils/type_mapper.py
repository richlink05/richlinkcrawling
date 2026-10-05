"""크롤링 원본 표현 → 홈해버 API가 요구하는 고정값으로 변환.

홈해버 API는 type/status가 정해진 문자열이 아니면 insert 자체를 거부한다고
명시했다. 크롤링 사이트마다 "생숙", "주상복합", "분양완료" 같은 다른 표현을
쓰므로, 여기서 매핑표를 거쳐 변환하고 매핑 실패 시 None을 반환해 호출부가
전송을 건너뛰게 한다.
"""
from __future__ import annotations

from backend.models.enums import ListingStatus, PropertyType

# 왼쪽 키는 공백 제거 + 소문자 비교 없이 "사이트에서 흔히 쓰는 원본 표현" 그대로 기재한다.
# 새 사이트를 추가하다가 매핑 안 되는 표현이 나오면 이 표에 추가하면 된다.
_TYPE_MAP: dict[str, PropertyType] = {
    "아파트": PropertyType.APARTMENT,
    "민간임대아파트": PropertyType.APARTMENT,
    "도시형생활주택": PropertyType.APARTMENT,  # 홈해버에 별도 카테고리가 없어 가장 가까운 값으로 매핑
    "타운하우스": PropertyType.APARTMENT,  # 위와 동일한 이유
    "주상복합": PropertyType.APARTMENT,
    "오피스텔": PropertyType.OFFICETEL,
    "생활숙박시설": PropertyType.LIVING_ACCOMMODATION,
    "생활형숙박시설": PropertyType.LIVING_ACCOMMODATION,
    "생숙": PropertyType.LIVING_ACCOMMODATION,
    "지식산업센터": PropertyType.KNOWLEDGE_INDUSTRY_CENTER,
    "지산": PropertyType.KNOWLEDGE_INDUSTRY_CENTER,
    "상가": PropertyType.COMMERCIAL,
    "근린생활시설": PropertyType.COMMERCIAL,
    "근생": PropertyType.COMMERCIAL,
}

_STATUS_MAP: dict[str, ListingStatus] = {
    "분양예정": ListingStatus.UPCOMING,
    "분양중": ListingStatus.ONGOING,
    "분양마감": ListingStatus.CLOSED,
    "마감": ListingStatus.CLOSED,
    "분양완료": ListingStatus.CLOSED,
    "완판": ListingStatus.CLOSED,
}


def map_property_type(raw_type: str) -> PropertyType | None:
    """크롤링 원본 분양 유형 표현을 홈해버가 허용하는 값으로 변환한다.

    매핑표에 없는 표현이면 None을 반환한다 — 호출부는 이 경우 전송을 건너뛰고
    SubmissionStatus.SKIPPED로 남겨야 한다.
    """
    return _TYPE_MAP.get(raw_type.strip())


def map_listing_status(raw_status: str | None) -> ListingStatus | None:
    """크롤링 원본 상태 표현을 홈해버가 허용하는 값으로 변환한다.

    raw_status가 없거나 매핑표에 없으면 None을 반환한다 — 이 경우 status
    필드 자체를 생략해서 보내면 홈해버 서버가 기본값(분양예정)을 채워준다.
    """
    if raw_status is None:
        return None
    return _STATUS_MAP.get(raw_status.strip())
