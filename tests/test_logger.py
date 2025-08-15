"""Test for logger module."""

import logging
import tempfile
from pathlib import Path

import pytest

from src.utils.logger import LogConfig, TradingLogger, get_logger, setup_logging


class TestLoggerSetup:
    """Test logger setup and configuration."""
    
    def test_setup_logging_default(self):
        """Test default logging setup."""
        setup_logging()
        logger = get_logger("test")
        assert logger.level == logging.INFO
    
    def test_setup_logging_custom_config(self):
        """Test logging setup with custom configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = LogConfig(
                level="DEBUG",
                log_dir=temp_dir,
                console_enabled=True,
                file_enabled=True
            )
            setup_logging(config)
            
            logger = get_logger("test_custom")
            assert logger.level == logging.DEBUG
            
            # Check that log file was created
            log_files = list(Path(temp_dir).glob("*.log"))
            assert len(log_files) > 0
    
    def test_get_logger(self):
        """Test getting logger instance."""
        logger1 = get_logger("test.module1")
        logger2 = get_logger("test.module2")
        logger3 = get_logger("test.module1")
        
        assert logger1.name == "test.module1"
        assert logger2.name == "test.module2"
        assert logger1 is logger3  # Same logger instance


class TestTradingLogger:
    """Test specialized trading logger."""
    
    def test_order_placed(self, caplog):
        """Test order placed logging."""
        logger = TradingLogger("test_trading")
        
        with caplog.at_level(logging.INFO):
            logger.order_placed("AAPL", 100, "LIMIT", 150.00)
        
        assert "Order placed: LIMIT 100 AAPL @ $150.0" in caplog.text
    
    def test_order_filled(self, caplog):
        """Test order filled logging."""
        logger = TradingLogger("test_trading")
        
        with caplog.at_level(logging.INFO):
            logger.order_filled("ORD123", "AAPL", 100, 150.50)
        
        assert "Order filled: ORD123 - 100 AAPL @ $150.5" in caplog.text
    
    def test_position_opened(self, caplog):
        """Test position opened logging."""
        logger = TradingLogger("test_trading")
        
        with caplog.at_level(logging.INFO):
            logger.position_opened("AAPL", 100, 150.00)
        
        assert "Position opened: 100 AAPL @ $150.0" in caplog.text
    
    def test_position_closed(self, caplog):
        """Test position closed logging."""
        logger = TradingLogger("test_trading")
        
        with caplog.at_level(logging.INFO):
            logger.position_closed("AAPL", 100, 150.00, 155.00, 500.00)
        
        assert "Position closed: AAPL P&L: $500.00" in caplog.text
        assert "(150.00 -> 155.00)" in caplog.text
    
    def test_risk_alert(self, caplog):
        """Test risk alert logging."""
        logger = TradingLogger("test_trading")
        
        with caplog.at_level(logging.WARNING):
            logger.risk_alert(
                "POSITION_LIMIT",
                "Position limit exceeded",
                symbol="AAPL",
                current=10,
                limit=5
            )
        
        assert "Risk Alert [POSITION_LIMIT]: Position limit exceeded" in caplog.text
    
    def test_strategy_signal(self, caplog):
        """Test strategy signal logging."""
        logger = TradingLogger("test_trading")
        
        with caplog.at_level(logging.INFO):
            logger.strategy_signal("MomentumBreakout", "AAPL", "BUY", 0.85)
        
        assert "Strategy signal: MomentumBreakout - BUY AAPL (confidence: 0.85)" in caplog.text