"""환경설정 및 공용 로거 검증 테스트."""
import logging

from backend.config.settings import Settings, get_settings
from backend.utils.logger import get_logger


class TestSettings:
    """환경설정 로딩을 검증한다."""

    def test_settings_loads_defaults(self, settings: Settings) -> None:
        """기본값으로 Settings가 정상 생성되는지 확인한다."""
        assert settings.app_env in {"local", "dev", "staging", "prod"}
        assert settings.max_concurrent_spiders == 20
        assert 0 < settings.duplicate_similarity_threshold <= 1
        assert settings.homehaver_api_url.startswith("https://")
        assert settings.homehaver_api_batch_size == 50

    def test_get_settings_is_singleton(self) -> None:
        """get_settings()가 캐시된 동일 인스턴스를 반환하는지 확인한다."""
        get_settings.cache_clear()
        first = get_settings()
        second = get_settings()
        assert first is second


class TestLogger:
    """공용 로거의 4단계 레벨(INFO/WARNING/ERROR/SUCCESS)을 검증한다."""

    def test_logger_has_success_level(self) -> None:
        """SUCCESS 레벨이 등록되어 있고 25번 레벨인지 확인한다."""
        assert logging.getLevelName(25) == "SUCCESS"

    def test_logger_returns_named_logger(self) -> None:
        """get_logger가 요청한 이름의 로거를 반환하는지 확인한다."""
        logger = get_logger("richlink.test")
        assert logger.name == "richlink.test"
        assert hasattr(logger, "success")

    def test_logger_does_not_duplicate_handlers(self) -> None:
        """동일 이름으로 재호출해도 핸들러가 중복 추가되지 않는지 확인한다."""
        logger1 = get_logger("richlink.dedup")
        logger2 = get_logger("richlink.dedup")
        assert len(logger1.handlers) == 1
        assert logger1 is logger2
