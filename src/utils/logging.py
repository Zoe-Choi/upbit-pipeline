"""
Logging configuration and utilities.
"""
import logging
import sys
from typing import Optional

from src.config import get_config


def setup_logger(
    name: str,
    level: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """
    Setup and configure a logger.
    
    Args:
        name: Logger name
        level: Log level (defaults to config value)
        format_string: Custom format string
        
    Returns:
        Configured logger instance
    """
    config = get_config()
    log_level = level or config.log_level
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, log_level.upper()))
        
        formatter = logging.Formatter(
            format_string or 
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with the given name."""
    return setup_logger(name)
