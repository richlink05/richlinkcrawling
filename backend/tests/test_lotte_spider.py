"""LotteSpider.parse()가 목록 HTML을 올바르게 파싱하는지 검증한다.

아래 샘플 HTML은 실제 https://www.lottecastle.co.kr/aptInfo/lots/list.do 페이지를
저장해서 받은 마크업에서 카드 3개(.list_box)를 그대로 발췌한 것이다(2026-10
확인). 예전 버전은 실제 사이트에 맞춰보지 않은 추측 선택자(.sale-list 등)를
썼다가 실제로는 한 건도 못 뽑는 문제가 있었다 — 그래서 실제 마크업 그대로를
고정 테스트로 남겨 회귀를 방지한다.
"""
from __future__ import annotations

from backend.spiders.builders.lotte_spider import LotteSpider

_REAL_SAMPLE_HTML = """
<div class="list_area type1">
  <div class="list_box">
    <a href="/APT/AT00427/main/index.do" class="txt_box" target="_blank">
      <div class="txt"><span class="">분양예정</span><p class="tit">경기광주역 롯데캐슬 시그니처 2단지</p></div>
    </a>
    <div class="img"><img src="/files/etc/2026/8/202608200944554990.jpg" alt=""/></div>
    <div class="heart_icon" data-apt-nm="경기광주역 롯데캐슬 시그니처 2단지" data-apt-cd="AT00427"
         data-loctn="경기도 광주시 쌍령동 산 54-29일대" data-tot-houshd-cnt="1249"
         data-lots-dt="2026-10-31" data-movin-dt="" data-inqy-tel="1899-2340"
         data-lots-scdl-yn="Y" data-movin-scdl-yn=""></div>
  </div>
  <div class="list_box">
    <a href="/APT/AT00430/main/index.do" class="txt_box" target="_blank">
      <div class="txt"><span class="">분양중</span><p class="tit">상동역 롯데캐슬 시그니처</p></div>
    </a>
    <div class="img"><img src="/files/etc/2026/8/202608120450384810.jpg" alt=""/></div>
    <div class="heart_icon" data-apt-nm="상동역 롯데캐슬 시그니처" data-apt-cd="AT00430"
         data-loctn="경기도 부천시 원미구 상동 540-1번지" data-tot-houshd-cnt="1859"
         data-lots-dt="2026-08-14" data-movin-dt="2032-03-31" data-inqy-tel="1551-3555"
         data-lots-scdl-yn="" data-movin-scdl-yn="Y"></div>
  </div>
  <div class="list_box">
    <a href="/APT/AT00429/main/index.do" class="txt_box" target="_blank">
      <div class="txt"><span class="">분양중</span><p class="tit">정동 롯데캐슬 136</p></div>
    </a>
    <div class="img"><img src="/files/etc/2026/3/202603311112582120.jpg" alt=""/></div>
    <div class="heart_icon" data-apt-nm="정동 롯데캐슬 136" data-apt-cd="AT00429"
         data-loctn="서울특별시 중구 순화동 6-11번지 일원" data-tot-houshd-cnt="136"
         data-lots-dt="2026-04-17" data-movin-dt="2027-04-30" data-inqy-tel=""
         data-lots-scdl-yn="" data-movin-scdl-yn="Y"></div>
  </div>
  <div class="list_box">
    <!-- heart_icon(data-apt-nm) 자체가 없는 비정상 카드는 건너뛰어야 한다 -->
    <a href="/APT/AT99999/main/index.do" class="txt_box"><div class="txt"><p class="tit">깨진 카드</p></div></a>
  </div>
</div>
"""

_LIST_URL = "https://www.lottecastle.co.kr/aptInfo/lots/list.do"


class TestLotteSpiderParse:
    def test_parses_all_valid_cards(self) -> None:
        spider = LotteSpider(fetcher=None)  # parse()는 순수 함수라 fetcher 불필요

        items = spider.parse(_REAL_SAMPLE_HTML, source_url=_LIST_URL)

        assert len(items) == 3
        titles = [item.title for item in items]
        assert "깨진 카드" not in titles

    def test_extracts_fields_from_data_attributes(self) -> None:
        spider = LotteSpider(fetcher=None)

        items = spider.parse(_REAL_SAMPLE_HTML, source_url=_LIST_URL)
        first = items[0]

        assert first.title == "경기광주역 롯데캐슬 시그니처 2단지"
        assert first.city == "경기도"
        assert first.district == "광주시"
        assert first.phone == "1899-2340"
        assert first.builder_name == "롯데건설"
        assert first.raw_type == "아파트"
        assert first.raw_status == "분양예정"
        assert first.supply_count == 1249
        assert first.subscription_date is not None and first.subscription_date.isoformat() == "2026-10-31"
        assert first.move_in_date is None  # data-movin-dt가 빈 문자열이면 None 처리
        assert first.source_url == "https://www.lottecastle.co.kr/APT/AT00427/main/index.do"
        assert first.images[0].source_url == (
            "https://www.lottecastle.co.kr/files/etc/2026/8/202608200944554990.jpg"
        )
        assert first.spider_name == "lotte"

    def test_each_card_gets_its_own_unique_source_url(self) -> None:
        """같은 목록 페이지라도 카드마다 상세 URL이 달라야 중복판단이 올바르게 동작한다."""
        spider = LotteSpider(fetcher=None)

        items = spider.parse(_REAL_SAMPLE_HTML, source_url=_LIST_URL)

        source_urls = {item.source_url for item in items}
        assert len(source_urls) == 3  # 전부 서로 달라야 함 (목록 페이지 URL로 뭉뚱그려지면 안 됨)

    def test_handles_missing_phone_gracefully(self) -> None:
        spider = LotteSpider(fetcher=None)

        items = spider.parse(_REAL_SAMPLE_HTML, source_url=_LIST_URL)
        no_phone_item = next(item for item in items if item.title == "정동 롯데캐슬 136")

        assert no_phone_item.phone is None
        assert no_phone_item.move_in_date is not None
        assert no_phone_item.move_in_date.isoformat() == "2027-04-30"
