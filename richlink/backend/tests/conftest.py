"""pytest 전역 fixture 모음."""
import pytest

from backend.config.settings import Settings, get_settings


@pytest.fixture
def settings() -> Settings:
    """테스트용 기본 Settings 인스턴스를 반환한다."""
    get_settings.cache_clear()
    return get_settings()
