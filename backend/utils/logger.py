"""프로젝트 전역에서 사용하는 로거.

표준 logging 모듈에 SUCCESS 레벨을 추가하여
INFO / WARNING / ERROR / SUCCESS 네 가지로 로그를 구분한다.
"""
from __future__ import annotations

import logging
import sys

SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")


def _success(self: logging.Logger, message: str, *args: object, **kwargs: object) -> None:
    """logging.Logger에 success() 메서드를 동적으로 추가한다."""
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kwargs)  # noqa: SLF001


logging.Logger.success = _success  # type: ignore[attr-defined]

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """모듈 이름을 받아 설정된 로거를 반환한다.

    Spider, Service 등 모든 컴포넌트는 이 함수를 통해 로거를 얻는다.
    이미 핸들러가 설정되어 있으면 중복 설정하지 않는다.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
