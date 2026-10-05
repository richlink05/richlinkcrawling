"""Celery 애플리케이션 및 Beat 스케줄 정의.

참고: GitHub Actions(.github/workflows/collect.yml)로 주기 실행하는 게
기본 운영 방식이다. Celery/Redis는 "서버를 직접 운영하는 환경"을 쓰고
싶을 때의 대안으로만 남겨뒀다 — 둘 다 설정할 필요는 없다.

분양현장은 실시간으로 바뀌는 데이터가 아니라서(하루 4번씩 돌릴 필요 없음),
주 1회(매주 월요일 03:00 KST)만 실행하도록 스케줄을 잡았다.
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from backend.config.settings import get_settings

_settings = get_settings()

celery_app = Celery(
    "richlink",
    broker=_settings.redis_url,
    include=["backend.scheduler.tasks"],
)

celery_app.conf.timezone = "Asia/Seoul"
celery_app.conf.beat_schedule = {
    "collect-weekly-monday-03:00": {
        "task": "backend.scheduler.tasks.run_pipeline",
        "schedule": crontab(hour=3, minute=0, day_of_week=1),  # 1 = 월요일
    },
}
