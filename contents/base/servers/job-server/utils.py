# utils.py
import os
from Logger import Logger, LogLevel
from enum import Enum, auto
from dotenv import load_dotenv

load_dotenv()

# Create an instance of the Logger class
logger = Logger()


def get_env_var(key: str, default=None):
    value = os.getenv(key, default)
    if value is None:
        logger.log(
            LogLevel.ERROR,
            f"Environment variable {key} not set and no default provided. Exiting.",
        )
        exit(1)
    return value


class ErrorCode(Enum):
    GENERAL = {"code": 500, "description": "General error"}
    NOT_FOUND = {"code": 404, "description": "Not found"}
