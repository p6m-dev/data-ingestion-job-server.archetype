import logging
from logging.handlers import RotatingFileHandler
from enum import Enum


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Logger:
    def __init__(self, log_file="app.log"):
        self.log_file = log_file
        self.logger = self.setup_logger()

    def setup_logger(self):
        logger = logging.getLogger("task_queue_logger")
        logger.setLevel(logging.DEBUG)

        handler = RotatingFileHandler(
            self.log_file, maxBytes=1024 * 1024, backupCount=5
        )
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        return logger

    def log(self, level: LogLevel, message: str):
        if level == LogLevel.DEBUG:
            self.logger.debug(message)
        elif level == LogLevel.INFO:
            self.logger.info(message)
        elif level == LogLevel.WARNING:
            self.logger.warning(message)
        elif level == LogLevel.ERROR:
            self.logger.error(message)
        elif level == LogLevel.CRITICAL:
            self.logger.critical(message)
        else:
            raise ValueError(f"Invalid log level: {level.value}")
