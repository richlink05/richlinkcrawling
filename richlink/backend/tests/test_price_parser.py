"""한글 가격 표기 → 만원 단위 변환 검증 테스트."""
from __future__ import annotations

from backend.utils.price_parser import parse_price_range, parse_price_to_manwon


class TestParsePriceToManwon:
    def test_parses_eok_only(self) -> None:
        assert parse_price_to_manwon("22.8억") == 228_000

    def test_parses_eok_and_man_combined(self) -> None:
        assert parse_price_to_manwon("3억 5,000만원") == 35_000

    def test_returns_none_for_undecided_text(self) -> None:
        assert parse_price_to_manwon("미정") is None

    def test_returns_none_for_empty_string(self) -> None:
        assert parse_price_to_manwon("") is None


class TestParsePriceRange:
    def test_parses_range_with_tilde(self) -> None:
        assert parse_price_range("22.8억~25.3억") == (228_000, 253_000)

    def test_single_value_used_as_both_min_and_max(self) -> None:
        assert parse_price_range("22.8억") == (228_000, 228_000)

    def test_none_input_returns_none_tuple(self) -> None:
        assert parse_price_range(None) == (None, None)

    def test_undecided_text_returns_none_tuple(self) -> None:
        assert parse_price_range("미정") == (None, None)
