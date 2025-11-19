"""
Logger Setup
Configures structured logging with Loguru
"""
import sys
from pathlib import Path
from loguru import logger
from typing import Dict, Any


def setup_logger(config: Dict[str, Any]):
    """
    Setup logger with configuration
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured logger instance
    """
    # Remove default logger
    logger.remove()
    
    # Get logging configuration
    log_config = config.get('logging', {})
    log_level = log_config.get('level', 'INFO')
    
    # Formato simplificado e funcional
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    handlers = log_config.get('handlers', ['console', 'file'])
    
    # Console handler
    if 'console' in handlers:
        logger.add(
            sys.stdout,
            format=log_format,
            level=log_level,
            colorize=True,
            backtrace=True,
            diagnose=True
        )
    
    # File handler
    if 'file' in handlers or 'rotating_file' in handlers:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / "urion.log"
        
        logger.add(
            str(log_file),
            format=log_format,
            level=log_level,
            rotation="10 MB",
            retention=10,
            compression="zip",
            backtrace=True,
            diagnose=True,
            enqueue=True  # Thread-safe
        )
    
    # Error file handler
    error_log = log_dir / "error.log"
    logger.add(
        str(error_log),
        format=log_format,
        level="ERROR",
        rotation="1 MB",
        retention=20,
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True
    )
    
    logger.info(f"Logger initialized with level: {log_level}")
    
    return logger
