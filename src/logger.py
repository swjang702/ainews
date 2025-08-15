"""Logging infrastructure for ainews."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from .config import LoggingConfig


class Logger:
    """Centralized logging setup for the application."""
    
    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls) -> 'Logger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def setup(self, config: LoggingConfig, name: str = "ainews") -> logging.Logger:
        """Setup logging configuration."""
        if self._logger is not None:
            return self._logger
            
        # Create logger
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, config.level.upper()))
        
        # Clear any existing handlers
        self._logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)
        
        # File handler with rotation
        log_file = Path(config.file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=config.max_file_size_mb * 1024 * 1024,
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, config.level.upper()))
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        self._logger.propagate = False
        
        return self._logger
    
    def get_logger(self) -> logging.Logger:
        """Get the configured logger instance."""
        if self._logger is None:
            raise RuntimeError("Logger not configured. Call setup() first.")
        return self._logger


def get_logger() -> logging.Logger:
    """Get the application logger."""
    return Logger().get_logger()


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """Setup logging and return logger instance."""
    return Logger().setup(config)