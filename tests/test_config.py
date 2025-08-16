"""Test for configuration module."""

import os
from unittest.mock import patch

import pytest

from src.config.constants import (
    AssetType, MarketSession, OrderAction, OrderStatus,
    OrderType, PositionStatus, TimeInForce, TradingMode
)
from src.config.settings import (
    DatabaseSettings, SchwabSettings, Settings, SystemSettings,
    TradingSettings, get_settings
)


class TestConstants:
    """Test constants and enums."""
    
    def test_trading_mode_enum(self):
        """Test TradingMode enum values."""
        assert TradingMode.DISCOVERY.value == "discovery"
        assert TradingMode.SELECTION.value == "selection"
        assert TradingMode.TRADING.value == "trading"
    
    def test_order_action_enum(self):
        """Test OrderAction enum values."""
        assert OrderAction.BUY.value == "BUY"
        assert OrderAction.SELL.value == "SELL"
        assert OrderAction.BUY_TO_COVER.value == "BUY_TO_COVER"
        assert OrderAction.SELL_SHORT.value == "SELL_SHORT"
    
    def test_order_status_enum(self):
        """Test OrderStatus enum values."""
        assert OrderStatus.PENDING.value == "PENDING"
        assert OrderStatus.FILLED.value == "FILLED"
        assert OrderStatus.CANCELLED.value == "CANCELLED"
        assert OrderStatus.REJECTED.value == "REJECTED"


class TestSettings:
    """Test settings configuration."""
    
    def test_schwab_settings_defaults(self):
        """Test Schwab settings default values."""
        settings = SchwabSettings(
            api_key="test_key",
            app_secret="test_secret"
        )
        assert settings.api_key == "test_key"
        assert settings.app_secret == "test_secret"
        assert settings.callback_url == "https://127.0.0.1:8182"
        assert settings.token_path == "config/token.json"
    
    def test_database_settings_defaults(self):
        """Test database settings default values."""
        settings = DatabaseSettings()
        assert settings.database_url == "postgresql://user:password@localhost/trading"
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.pool_size == 20
        assert settings.max_overflow == 40
        assert settings.echo is False
    
    def test_trading_settings_defaults(self):
        """Test trading settings default values."""
        settings = TradingSettings()
        assert settings.initial_capital == 100000.0
        assert settings.max_position_size == 10000.0
        assert settings.max_daily_loss == 2000.0
        assert settings.risk_per_trade == 0.01
        assert settings.stop_loss_percent == 0.02
        assert settings.take_profit_percent == 0.05
    
    def test_system_settings_defaults(self):
        """Test system settings default values."""
        settings = SystemSettings()
        assert settings.environment == "development"
        assert settings.debug is True
        assert settings.log_level == "INFO"
        assert settings.gui_theme == "dark"
        assert settings.enable_paper_trading is True
        assert settings.enable_real_trading is False
    
    @patch.dict(os.environ, {
        "SCHWAB__API_KEY": "env_key",
        "SCHWAB__APP_SECRET": "env_secret",
        "SYSTEM__ENVIRONMENT": "production",
        "SYSTEM__DEBUG": "false"
    })
    def test_settings_from_env(self):
        """Test loading settings from environment variables."""
        # Clear the cache to force reload
        get_settings.cache_clear()
        
        settings = get_settings()
        assert settings.schwab.api_key == "env_key"
        assert settings.schwab.app_secret == "env_secret"
        assert settings.system.environment == "production"
        assert settings.system.debug is False
        assert settings.is_production is True
        assert settings.is_development is False
    
    def test_get_database_url(self):
        """Test database URL selection based on environment."""
        settings = Settings(
            schwab=SchwabSettings(api_key="test", app_secret="test"),
            system=SystemSettings(environment="development")
        )
        
        # Should always use configured database URL
        url = settings.get_database_url()
        assert "postgresql://" in url
        assert url == settings.database.database_url
        
        # Production should use configured URL
        settings.system.environment = "production"
        settings.database.database_url = "postgresql://user:pass@host/db"
        prod_url = settings.get_database_url()
        assert prod_url == "postgresql://user:pass@host/db"