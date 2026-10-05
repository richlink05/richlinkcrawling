"""LotteSpider.parse()가 목록 HTML을 올바르게 파싱하는지 검증한다."""
from __future__ import annotations

from backend.spiders.builders.lotte_spider import LotteSpider

_SAMPLE_HTML = """
<html><body>
  <div class="sale-list">
    <div class="sale-item">
      <div class="sale-item__title">힐스테이트 강남 (예시)</div>
      <div class="sale-item__address">서울특별시 강남구 테헤란로 123</div>
      <div class="sale-item__tel">02-1234-5678</div>
      <div class="sale-item__type">아파트</div>
      <div class="sale-item__status">분양중</div>
      <div class="sale-item__unit-type" data-price="22.8억">84A</div>
      <div class="sale-item__unit-type" data-price="25.3억">84B</div>
      <div class="sale-item__thumb"><img src="https://example.com/a.jpg" /></div>
    </div>
    <div class="sale-item">
      <div class="sale-item__title">현장명 없음 테스트</div>
      <!-- 주소 요소가 없어 스킵되어야 하는 카드 -->
    </div>
  </div>
</body></html>
"""


class TestLotteSpiderParse:
    def test_parse_extracts_project_fields(self) -> None:
        spider = LotteSpider(fetcher=None)  # parse()는 순수 함수라 fetcher 불필요

        items = spider.parse(_SAMPLE_HTML, source_url="https://www.lottecastle.co.kr/Sale/List")

        assert len(items) == 1
        item = items[0]
        assert item.title == "힐스테이트 강남 (예시)"
        assert item.city == "서울특별시"
        assert item.district == "강남구"
        assert item.phone == "02-1234-5678"
        assert item.builder_name == "롯데건설"
        assert item.raw_type == "아파트"
        assert item.raw_status == "분양중"
        assert [u.raw_type for u in item.unit_types] == ["84A", "84B"]
        assert item.unit_types[0].price_text == "22.8억"
        assert item.images[0].source_url == "https://example.com/a.jpg"
        assert item.spider_name == "lotte"

    def test_parse_skips_cards_without_address(self) -> None:
        spider = LotteSpider(fetcher=None)

        items = spider.parse(_SAMPLE_HTML, source_url="https://example.com")

        titles = [item.title for item in items]
        assert "현장명 없음 테스트" not in titles
