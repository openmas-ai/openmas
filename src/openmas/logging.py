"""Logging configuration for OpenMAS."""

import logging
import sys
from typing import Optional, Union, cast

import structlog
from structlog.stdlib import BoundLogger
from structlog.types import Processor


def configure_logging(
    log_level: Union[str, int] = logging.INFO,
    json_format: bool = False,
    timestamp_key: str = "timestamp",
    additional_processors: Optional[list[Processor]] = None,
) -> None:
    """Configure logging for the application.

    Args:
        log_level: The log level to use (default: INFO)
        json_format: Whether to output logs in JSON format (default: False)
        timestamp_key: The key to use for the timestamp in the log output (default: timestamp)
        additional_processors: Additional processors to add to the structlog processing pipeline
    """
    level = log_level.upper() if isinstance(log_level, str) else log_level

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", key=timestamp_key),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if additional_processors:
        processors.extend(additional_processors)

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True, exception_formatter=structlog.dev.plain_traceback))

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=cast(Union[int, str, None], level),
    )


def get_logger(name: str) -> BoundLogger:
    """Get a logger instance.

    Args:
        name: The name of the logger

    Returns:
        A configured logger
    """
    return cast(BoundLogger, structlog.get_logger(name))
