"""Logging configuration and utilities for the trading system."""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class LogConfig(BaseModel):
    """Logging configuration."""
    
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    
    # File logging
    log_dir: str = "logs"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    # Console logging
    console_enabled: bool = True
    console_level: str = "INFO"
    
    # File logging per module
    file_enabled: bool = True
    separate_error_log: bool = True


def setup_logging(config: Optional[LogConfig] = None) -> None:
    """Set up logging configuration for the entire application."""
    if config is None:
        config = LogConfig()
    
    # Create logs directory
    log_dir = Path(config.log_dir)
    log_dir.mkdir(exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    if config.console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.console_level))
        console_formatter = logging.Formatter(config.format, config.date_format)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if config.file_enabled:
        # Main log file
        log_file = log_dir / f"trading_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(config.format, config.date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Separate error log
        if config.separate_error_log:
            error_file = log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
            error_handler = logging.handlers.RotatingFileHandler(
                filename=error_file,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(file_formatter)
            root_logger.addHandler(error_handler)
    
    # Configure third-party loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('websockets').setLevel(logging.WARNING)
    
    root_logger.info("Logging configured successfully")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(name)


class TradingLogger:
    """Specialized logger for trading operations with structured logging."""
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
    
    def order_placed(self, symbol: str, quantity: int, order_type: str, price: Optional[float] = None):
        """Log order placement."""
        extra = {
            'event': 'order_placed',
            'symbol': symbol,
            'quantity': quantity,
            'order_type': order_type,
            'price': price
        }
        self.logger.info(
            f"Order placed: {order_type} {quantity} {symbol}" + 
            (f" @ ${price}" if price else ""),
            extra=extra
        )
    
    def order_filled(self, order_id: str, symbol: str, quantity: int, price: float):
        """Log order execution."""
        extra = {
            'event': 'order_filled',
            'order_id': order_id,
            'symbol': symbol,
            'quantity': quantity,
            'price': price
        }
        self.logger.info(
            f"Order filled: {order_id} - {quantity} {symbol} @ ${price}",
            extra=extra
        )
    
    def position_opened(self, symbol: str, quantity: int, entry_price: float):
        """Log position opening."""
        extra = {
            'event': 'position_opened',
            'symbol': symbol,
            'quantity': quantity,
            'entry_price': entry_price
        }
        self.logger.info(
            f"Position opened: {quantity} {symbol} @ ${entry_price}",
            extra=extra
        )
    
    def position_closed(self, symbol: str, quantity: int, entry_price: float, 
                       exit_price: float, profit_loss: float):
        """Log position closing."""
        extra = {
            'event': 'position_closed',
            'symbol': symbol,
            'quantity': quantity,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'profit_loss': profit_loss
        }
        self.logger.info(
            f"Position closed: {symbol} P&L: ${profit_loss:.2f} "
            f"({entry_price:.2f} -> {exit_price:.2f})",
            extra=extra
        )
    
    def risk_alert(self, alert_type: str, message: str, **kwargs):
        """Log risk management alerts."""
        extra = {
            'event': 'risk_alert',
            'alert_type': alert_type,
            **kwargs
        }
        self.logger.warning(f"Risk Alert [{alert_type}]: {message}", extra=extra)
    
    def strategy_signal(self, strategy: str, symbol: str, action: str, confidence: float):
        """Log strategy signals."""
        extra = {
            'event': 'strategy_signal',
            'strategy': strategy,
            'symbol': symbol,
            'action': action,
            'confidence': confidence
        }
        self.logger.info(
            f"Strategy signal: {strategy} - {action} {symbol} (confidence: {confidence:.2f})",
            extra=extra
        )