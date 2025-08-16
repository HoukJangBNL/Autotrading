"""Configuration settings management using Pydantic."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class SchwabSettings(BaseSettings):
    """Schwab API configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="SCHWAB_",
        case_sensitive=False
    )
    
    api_key: str
    app_secret: str
    callback_url: str = "https://127.0.0.1:8182"
    account_number: Optional[str] = None
    token_path: str = "config/token.json"


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="",  # Remove prefix to match .env file
        case_sensitive=False
    )
    
    database_url: str = "postgresql://user:password@localhost/trading"
    redis_url: str = "redis://localhost:6379/0"
    pool_size: int = 20
    max_overflow: int = 40
    pool_timeout: int = 30
    echo: bool = False


class TradingSettings(BaseSettings):
    """Trading configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="TRADING_",
        case_sensitive=False
    )
    
    initial_capital: float = 100000.0
    max_position_size: float = 10000.0
    max_daily_loss: float = 2000.0
    risk_per_trade: float = 0.01
    max_positions: int = 10
    max_daily_trades: int = 100
    
    # Risk management
    stop_loss_percent: float = 0.02
    take_profit_percent: float = 0.05
    trailing_stop_percent: float = 0.01
    
    # Circuit breakers
    max_drawdown_percent: float = 0.05
    consecutive_losses_limit: int = 5


class SystemSettings(BaseSettings):
    """System configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="SYSTEM_",
        case_sensitive=False
    )
    
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    
    # GUI settings
    gui_theme: str = "dark"
    gui_update_interval: int = 1000  # milliseconds
    
    # Performance
    stream_buffer_size: int = 1000
    batch_insert_size: int = 100
    
    # Feature flags
    enable_paper_trading: bool = True
    enable_real_trading: bool = False
    enable_notifications: bool = True
    enable_backtesting: bool = True


class Settings(BaseSettings):
    """Main settings class combining all configurations."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore"  # Ignore extra environment variables
    )
    
    # Sub-configurations
    schwab: SchwabSettings
    database: DatabaseSettings
    trading: TradingSettings
    system: SystemSettings
    
    # Paths
    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Path = project_root / "data"
    logs_dir: Path = project_root / "logs"
    config_dir: Path = project_root / "config"
    
    def __init__(self, **kwargs):
        # Initialize sub-configurations if not provided
        if 'schwab' not in kwargs:
            kwargs['schwab'] = SchwabSettings()
        if 'database' not in kwargs:
            kwargs['database'] = DatabaseSettings()
        if 'trading' not in kwargs:
            kwargs['trading'] = TradingSettings()
        if 'system' not in kwargs:
            kwargs['system'] = SystemSettings()
            
        super().__init__(**kwargs)
        
        # Create necessary directories
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.config_dir.mkdir(exist_ok=True)
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.system.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.system.environment.lower() == "development"
    
    def get_database_url(self) -> str:
        """Get appropriate database URL based on environment."""
        # Always use the configured database URL (PostgreSQL)
        return self.database.database_url


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    from dotenv import load_dotenv
    load_dotenv()  # Ensure .env is loaded
    return Settings()


# Create a global settings instance
settings = get_settings()