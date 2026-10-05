"""한글 분양가 표기를 홈해버가 요구하는 "만원 단위 숫자"로 변환.

예: "22.8억" → 228000, "3억 5,000만원" → 35000, "22.8억~25.3억" → (228000, 253000)
크롤링 사이트마다 표기가 제각각이라 완벽한 처리는 불가능하지만, 억/만 조합
표기는 대부분 커버한다. 해석할 수 없는 문자열("미정", "협의" 등)은 None을
반환해 그 필드를 생략하게 한다 (홈해버 쪽도 선택 필드라 비워도 문제없음).
"""
from __future__ import annotations

import re

_EOK_MAN_PATTERN = re.compile(
    r"(?:(?P<eok>\d+(?:\.\d+)?)\s*억)?\s*(?:(?P<man>[\d,]+)\s*만)?"
)
_RANGE_SPLIT_PATTERN = re.compile(r"[~\-]")


def parse_price_to_manwon(text: str) -> float | None:
    """"3억 5,000만원" 같은 단일 가격 문자열을 만원 단위 숫자로 변환한다.

    억/만 패턴이 전혀 없으면(문자 자체가 없거나 "미정" 등) None을 반환한다.
    """
    cleaned = text.strip()
    if not cleaned:
        return None

    match = _EOK_MAN_PATTERN.search(cleaned)
    if match is None:
        return None

    eok_str, man_str = match.group("eok"), match.group("man")
    if eok_str is None and man_str is None:
        return None

    total_manwon = 0.0
    if eok_str is not None:
        total_manwon += float(eok_str) * 10_000
    if man_str is not None:
        total_manwon += float(man_str.replace(",", ""))
    return total_manwon


def parse_price_range(text: str | None) -> tuple[float | None, float | None]:
    """"22.8억~25.3억" 같은 범위 표기를 (최소, 최대) 만원 단위로 변환한다.

    "~"나 "-"로 구간을 나눈 뒤 각각 parse_price_to_manwon을 적용한다.
    범위 표기가 아니면 동일한 값을 최소/최대로 반환한다.
    """
    if text is None or not text.strip():
        return None, None

    parts = [part for part in _RANGE_SPLIT_PATTERN.split(text) if part.strip()]
    if not parts:
        return None, None

    parsed = [parse_price_to_manwon(part) for part in parts]
    parsed = [value for value in parsed if value is not None]
    if not parsed:
        return None, None
    if len(parsed) == 1:
        return parsed[0], parsed[0]
    return min(parsed), max(parsed)
