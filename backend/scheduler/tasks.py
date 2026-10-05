"""Celery 태스크 정의 (Celery로 셀프 호스팅하는 경우에만 사용).

기본 운영 방식은 GitHub Actions + backend/scheduler/run_once.py다. 이
파일은 서버를 직접 띄워 Celery Beat로 운영하고 싶은 경우의 대안이며,
run_once.py의 run_once_async()를 그대로 재사용한다.
"""
from __future__ import annotations

import asyncio

from backend.scheduler.celery_app import celery_app
from backend.scheduler.run_once import run_once_async
from backend.utils.logger import get_logger

logger = get_logger("scheduler.tasks")


@celery_app.task(name="backend.scheduler.tasks.run_pipeline")
def run_pipeline() -> None:
    """Celery Beat가 주기적으로 호출하는 진입점 태스크."""
    asyncio.run(run_once_async())
