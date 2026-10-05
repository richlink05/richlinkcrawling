"""Celery Beat 스케줄이 주 1회(월요일 03:00)로 설정되어 있는지 검증한다.

참고: 기본 운영 방식은 GitHub Actions이고, 이 스케줄은 Celery로 셀프
호스팅할 때만 쓰는 대안이다.
"""
from __future__ import annotations

from backend.scheduler.celery_app import celery_app


class TestBeatSchedule:
    def test_has_single_weekly_entry(self) -> None:
        assert len(celery_app.conf.beat_schedule) == 1

    def test_entry_targets_monday_at_3am(self) -> None:
        entry = next(iter(celery_app.conf.beat_schedule.values()))
        assert next(iter(entry["schedule"].hour)) == 3
        assert next(iter(entry["schedule"].day_of_week)) == 1

    def test_task_name_points_to_run_pipeline(self) -> None:
        tasks = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
        assert tasks == {"backend.scheduler.tasks.run_pipeline"}
