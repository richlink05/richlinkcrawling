"""Project(RichLink 내부 모델) → 홈해버 API 요청 JSON 변환.

홈해버 쪽 계약(2026-10 확인)에 맞춰 필드명을 정확히 맞춘다:
- title, type, address, builder_name, status, price_min/max, area_min/max
- manager_name/manager_phone는 보내지 않음(홈해버가 "신경 쓰지 말라"고 명시)
- lat/lng를 모르면 아예 생략 — 홈해버 서버가 address로 카카오 지오코딩을 자동으로 해줌
- images: thumbnail_url(대표 1장) + images(나머지, url+category)
- client_ref: RichLink 쪽 Project.id를 그대로 보내서, 응답에서 어떤 요청이
  어떤 결과인지 매칭한다 (홈해버 DB에는 저장 안 되는 응답용 값).
"""
from __future__ import annotations

from backend.models.project import Project


def build_listing_payload(project: Project) -> dict:
    """Project 1건을 홈해버 API가 기대하는 JSON 딕셔너리로 변환한다.

    호출 전에 project.mapped_type이 이미 채워져 있어야 한다(=None이면 호출부가
    애초에 전송 대상에서 제외해야 함 — type은 홈해버 쪽 필수값이라서).
    """
    payload: dict = {
        "client_ref": str(project.id),
        "title": project.title[:50],
        "type": project.mapped_type,
        "address": project.address,
    }

    if project.mapped_status is not None:
        payload["status"] = project.mapped_status
    if project.builder_name:
        payload["builder_name"] = project.builder_name
    if project.lat is not None and project.lng is not None:
        payload["lat"] = project.lat
        payload["lng"] = project.lng
    if project.price_min is not None:
        payload["price_min"] = project.price_min
    if project.price_max is not None:
        payload["price_max"] = project.price_max
    if project.area_min is not None:
        payload["area_min"] = project.area_min
    if project.area_max is not None:
        payload["area_max"] = project.area_max
    if project.supply_count is not None:
        payload["supply_count"] = project.supply_count
    if project.move_in_date is not None:
        payload["move_in_date"] = project.move_in_date.isoformat()
    if project.subscription_date is not None:
        payload["subscription_date"] = project.subscription_date.isoformat()
    if project.description:
        payload["description"] = project.description
    if project.thumbnail_url:
        payload["thumbnail_url"] = project.thumbnail_url

    images = [
        {"image_url": image.image_url, "category": image.category.value}
        for image in project.images
    ]
    if images:
        payload["images"] = images

    return payload
