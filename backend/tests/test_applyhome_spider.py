"""청약홈 API Spider 검증.

샘플 값은 한국부동산원 '청약홈 분양정보 조회 서비스 활용가이드'(260129)의
응답 예시(APT: 창동 다우아트리체, 도시형: 힐스테이트 청량리 메트로블)를 그대로 썼다.
실제 서버에는 접속하지 않고 httpx.MockTransport로 응답을 흉내 낸다.
"""
from __future__ import annotations

from datetime import date

import httpx
import pytest

from backend.config.settings import Settings
from backend.spiders.subscription.applyhome_spider import (
    ApplyhomeApiError,
    ApplyhomeSpider,
    _compute_status,
    _format_phone,
    _month_end,
)

_KEY = "TESTKEY_abc123"
_TODAY = date(2022, 5, 25)

_APT_ROW = {
    "HOUSE_MANAGE_NO": "2022000248",
    "PBLANC_NO": "2022000248",
    "HOUSE_NM": "창동 다우아트리체 주상복합 아파트",
    "HSSPLY_ADRES": "서울특별시 도봉구 창동 662-7번지 외 12필지",
    "TOT_SUPLY_HSHLDCO": 89,
    "RCRIT_PBLANC_DE": "2022-05-12",
    "RCEPT_BGNDE": "2022-05-23",
    "RCEPT_ENDDE": "2022-05-26",
    "PRZWNER_PRESNATN_DE": "2022-06-02",
    "CNTRCT_CNCLS_BGNDE": "2022-06-13",
    "CNTRCT_CNCLS_ENDDE": "2022-06-15",
    "HMPG_ADRES": "http://www.dawartriche.com/",
    "CNSTRCT_ENTRPS_NM": "강산건설㈜",
    "MDHS_TELNO": "16684888",
    "BSNS_MBY_NM": "주식회사 하나자산신탁",
    "MVN_PREARNGE_YM": "202502",
    "PBLANC_URL": "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2022000248&pblancNo=2022000248",
}

_URBTY_ROW = {
    "HOUSE_MANAGE_NO": "2022950004",
    "PBLANC_NO": "2022950004",
    "HOUSE_NM": "힐스테이트 청량리 메트로블 (도시형생활주택)",
    "SEARCH_HOUSE_SECD": "0201",
    "HOUSE_DTL_SECD_NM": "도시형생활주택",
    "HSSPLY_HSHLDCO": "서울특별시 동대문구 용두동 26-14번지 일원",  # 가이드 표기 그대로(항목명이 다름)
    "TOT_SUPLY_HSHLDCO": "213",
    "RCRIT_PBLANC_DE": "2022-02-10",
    "SUBSCRPT_RCEPT_BGNDE": "2022-02-21",
    "SUBSCRPT_RCEPT_ENDDE": "2022-02-22",
    "CNTRCT_CNCLS_ENDDE": "2022-03-04",
    "MDHS_TELNO": "0234520100",
    "MVN_PREARNGE_YM": "202507",
    "PBLANC_URL": "https://www.applyhome.co.kr/ai/aia/selectPRMOLttotPblancDetailView.do?houseManageNo=2022950004&pblancNo=2022950004",
}

_APT_UNITS = [
    {"HOUSE_TY": "058.8500A", "SUPLY_AR": "80.3800", "LTTOT_TOP_AMOUNT": "80720"},
    {"HOUSE_TY": "084.9000B", "SUPLY_AR": "110.1", "LTTOT_TOP_AMOUNT": "112,400"},
]
_URBTY_UNITS = [
    {"EXCLUSE_AR": 26, "SUPLY_AMOUNT": "53,740"},
    {"EXCLUSE_AR": "36.5", "SUPLY_AMOUNT": "70,000"},
]


def _spider(handler, per_page: int = 100) -> ApplyhomeSpider:  # noqa: ANN001
    settings = Settings(applyhome_api_key=_KEY, applyhome_lookback_days=30, applyhome_per_page=per_page)
    return ApplyhomeSpider(
        settings=settings, transport=httpx.MockTransport(handler), today=_TODAY, retry_base_delay=0
    )


def _json(data: list[dict], match_count: int | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        json={"currentCount": len(data), "data": data, "matchCount": match_count or len(data)},
    )


class TestMapping:
    def test_apt_row_maps_all_fields(self) -> None:
        spider = ApplyhomeSpider(settings=Settings(applyhome_api_key=_KEY))
        from backend.base.schemas import UnitTypeData

        units = [UnitTypeData(raw_type="058.8500A", area_sqm=58.85, price_text="80720만원")]

        item = spider._to_project("apt", _APT_ROW, units, _TODAY)

        assert item is not None
        assert item.title == "창동 다우아트리체 주상복합 아파트"
        assert item.city == "서울특별시" and item.district == "도봉구"
        assert item.builder_name == "강산건설㈜"
        assert item.raw_type == "아파트"
        assert item.supply_count == 89
        assert item.subscription_date == date(2022, 5, 23)
        assert item.move_in_date == date(2025, 2, 28)
        assert item.phone == "1668-4888"
        assert item.raw_status == "분양중"  # 오늘(5/25)이 접수 시작(5/23) 이후 ~ 계약 종료(6/15) 이전
        assert item.source_url.startswith("https://www.applyhome.co.kr/")
        assert item.spider_name == "applyhome"
        assert "시행사: 주식회사 하나자산신탁" in (item.description or "")

    def test_urbty_row_uses_alternate_address_key_and_has_no_builder(self) -> None:
        spider = ApplyhomeSpider(settings=Settings(applyhome_api_key=_KEY))

        item = spider._to_project("urbty", _URBTY_ROW, [], _TODAY)

        assert item is not None
        assert item.address == "서울특별시 동대문구 용두동 26-14번지 일원"
        assert item.builder_name is None
        assert item.raw_type == "도시형생활주택"
        assert item.phone == "02-3452-0100"
        assert item.raw_status == "분양완료"  # 계약 종료(3/4)가 오늘보다 과거
        assert item.subscription_date == date(2022, 2, 21)

    def test_row_without_title_or_address_is_skipped(self) -> None:
        spider = ApplyhomeSpider(settings=Settings(applyhome_api_key=_KEY))

        assert spider._to_project("apt", {"HOUSE_NM": "이름만 있음"}, [], _TODAY) is None
        assert spider._to_project("apt", {"HSSPLY_ADRES": "주소만 있음"}, [], _TODAY) is None

    def test_missing_pblanc_url_falls_back_to_stable_key(self) -> None:
        spider = ApplyhomeSpider(settings=Settings(applyhome_api_key=_KEY))
        row = {k: v for k, v in _APT_ROW.items() if k != "PBLANC_URL"}

        item = spider._to_project("apt", row, [], _TODAY)

        assert item is not None
        assert item.source_url == "applyhome://apt/2022000248/2022000248"


class TestHelpers:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("16684888", "1668-4888"),
            ("0234520100", "02-3452-0100"),
            ("023452010", "02-345-2010"),
            ("0314567890", "031-456-7890"),
            ("01012345678", "010-1234-5678"),
            ("-", None),
            (None, None),
        ],
    )
    def test_format_phone(self, raw: str | None, expected: str | None) -> None:
        assert _format_phone(raw) == expected

    def test_month_end(self) -> None:
        assert _month_end("202502") == date(2025, 2, 28)
        assert _month_end("202412") == date(2024, 12, 31)
        assert _month_end("2025") is None
        assert _month_end("202513") is None

    def test_status_by_date(self) -> None:
        start, end = date(2026, 10, 10), date(2026, 10, 30)
        assert _compute_status(date(2026, 10, 9), start, end) == "분양예정"
        assert _compute_status(date(2026, 10, 10), start, end) == "분양중"
        assert _compute_status(date(2026, 10, 30), start, end) == "분양중"
        assert _compute_status(date(2026, 10, 31), start, end) == "분양완료"
        assert _compute_status(date(2026, 10, 31), None, end) is None


class TestCollect:
    async def test_collects_both_kinds_with_price_and_area_ranges(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            path = request.url.path
            if path.endswith("getAPTLttotPblancDetail"):
                return _json([_APT_ROW])
            if path.endswith("getUrbtyOfctlLttotPblancDetail"):
                return _json([_URBTY_ROW])
            if path.endswith("getAPTLttotPblancMdl"):
                return _json(_APT_UNITS)
            if path.endswith("getUrbtyOfctlLttotPblancMdl"):
                return _json(_URBTY_UNITS)
            return httpx.Response(404)

        items = await _spider(handler).collect()

        assert len(items) == 2
        apt = next(item for item in items if item.raw_type == "아파트")
        from backend.utils.listing_aggregator import aggregate_area_range, aggregate_price_range

        assert aggregate_price_range(apt.unit_types) == (80720.0, 112400.0)
        assert aggregate_area_range(apt.unit_types) == (58.85, 84.9)
        urbty = next(item for item in items if item.raw_type == "도시형생활주택")
        assert aggregate_price_range(urbty.unit_types) == (53740.0, 70000.0)
        assert aggregate_area_range(urbty.unit_types) == (26.0, 36.5)

        detail_requests = [r for r in seen if r.url.path.endswith("PblancDetail")]
        assert all(r.url.params["cond[RCRIT_PBLANC_DE::GTE]"] == "2022-04-25" for r in detail_requests)
        assert all(r.url.params["serviceKey"] == _KEY for r in seen)
        model_request = next(r for r in seen if r.url.path.endswith("getAPTLttotPblancMdl"))
        assert model_request.url.params["cond[HOUSE_MANAGE_NO::EQ]"] == "2022000248"

    async def test_follows_pagination(self) -> None:
        rows = [{**_APT_ROW, "HOUSE_MANAGE_NO": str(i), "PBLANC_NO": str(i), "PBLANC_URL": f"https://x/{i}"} for i in range(5)]

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("getAPTLttotPblancDetail"):
                page = int(request.url.params["page"])
                chunk = rows[(page - 1) * 2 : page * 2]
                return _json(chunk, match_count=5)
            if path.endswith("PblancDetail"):
                return _json([])
            return _json([])

        items = await _spider(handler, per_page=2).collect()

        assert len(items) == 5
        assert len({item.source_url for item in items}) == 5

    async def test_unit_lookup_failure_keeps_the_listing_without_price(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("getAPTLttotPblancDetail"):
                return _json([_APT_ROW])
            if path.endswith("PblancDetail"):
                return _json([])
            return httpx.Response(500)

        items = await _spider(handler).collect()

        assert len(items) == 1
        assert items[0].unit_types == []

    async def test_missing_key_returns_nothing_without_calling_api(self) -> None:
        called = False

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal called
            called = True
            return _json([])

        spider = ApplyhomeSpider(
            settings=Settings(applyhome_api_key=""), transport=httpx.MockTransport(handler), today=_TODAY
        )

        assert await spider.collect() == []
        assert called is False

    async def test_auth_failure_error_never_contains_the_key_or_url(self) -> None:
        spider = _spider(lambda request: httpx.Response(401, json={"msg": "bad key"}))

        async with httpx.AsyncClient(transport=spider._transport) as client:
            with pytest.raises(ApplyhomeApiError) as excinfo:
                await spider._get_json(client, "getAPTLttotPblancDetail", {"page": 1})

        message = str(excinfo.value)
        assert _KEY not in message
        assert "serviceKey" not in message and "odcloud" not in message
        assert "401" in message

    async def test_collect_logs_never_leak_the_key_on_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        items = await _spider(handler).collect()

        assert items == []
        captured = capsys.readouterr()
        assert _KEY not in captured.out + captured.err

    async def test_encoded_key_is_decoded_once(self) -> None:
        seen_keys: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_keys.append(request.url.params["serviceKey"])
            return _json([])

        settings = Settings(applyhome_api_key="abc%2Bdef%3D")
        spider = ApplyhomeSpider(
            settings=settings, transport=httpx.MockTransport(handler), today=_TODAY, retry_base_delay=0
        )
        await spider.collect()

        assert seen_keys and set(seen_keys) == {"abc+def="}

