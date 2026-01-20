"""로깅 유틸리티 - Singleton 패턴"""

import logging
import os


class SingletonType(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonType, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Logger(metaclass=SingletonType):
    def __init__(self):
        self._logger = logging.getLogger("opsnow-copilot")
        self._initialized = False
        self._init_default()

    def _init_default(self):
        """기본 콘솔 핸들러 설정"""
        if not self._initialized and not self._logger.handlers:
            # config.py의 LOGGING_LEVEL 사용 (lazy import)
            from src.config import LOGGING_LEVEL

            # root logger와 app logger 모두 설정
            logging.root.setLevel(LOGGING_LEVEL)
            self._logger.setLevel(LOGGING_LEVEL)

            logging_format = "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d %(funcName)s - %(message)s"

            console_handler = logging.StreamHandler()
            console_handler.setLevel(LOGGING_LEVEL)  # handler level도 설정
            console_handler.setFormatter(logging.Formatter(logging_format))
            self._logger.addHandler(console_handler)

            # root logger에도 handler를 붙여 다른 모듈 로그를 수집
            if not logging.root.handlers:
                root_handler = logging.StreamHandler()
                root_handler.setLevel(LOGGING_LEVEL)
                root_handler.setFormatter(logging.Formatter(logging_format))
                logging.root.addHandler(root_handler)

            self._logger.propagate = False
            self._initialized = True

            # 외부 라이브러리 로그 레벨 조정 (상세 로그 숨김)
            logging.getLogger("WDM").setLevel(logging.WARNING)
            logging.getLogger("selenium").setLevel(logging.WARNING)
            logging.getLogger("urllib3").setLevel(logging.WARNING)
            logging.getLogger("openai").setLevel(logging.WARNING)
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("httpcore").setLevel(logging.WARNING)

    def get(self):
        return self._logger
