"""Loguru-based logger configuration for Binance TA bot."""

import sys
from loguru import logger


def setup_logger(level: str = "INFO") -> None:
    """Configure loguru logger for the bot.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
    """
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
            "- <level>{message}</level>"
        ),
    )
    logger.add(
        "logs/ta_bot_{time:YYYYMMDD_HHMMSS}.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        enqueue=True,
    )
