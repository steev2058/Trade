from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "production"
    log_level: str = "INFO"
    timezone: str = "UTC"
    mode: str = "paper"

    master_key_base64: str = ""
    enable_encrypted_secrets: bool = True

    mt5_login: int | None = None
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    max_risk_per_trade: float = 0.02
    max_daily_loss: float = 0.05
    max_trades_per_day: int = 20
    max_concurrent_positions: int = 5

    default_symbol: str = "EURUSD"

    enable_smc_ict: bool = True
    enable_scalper: bool = True
    enable_news: bool = True
    enable_adaptive_weighting: bool = True
    enable_london_ny_session: bool = True

    bridge_api_base: str = ""
    bridge_token: str = ""

    auto_trading_enabled: bool = False
    auto_default_symbol: str = "XAUUSD.m"
    auto_default_lot: float = 0.01
    auto_cooldown_seconds: int = 120
    report_interval_seconds: int = 3600
    watch_symbols: str = "XAUUSD.m,BRENT.m"

    tick_interval_seconds: int = 3
    heartbeat_seconds: int = 60


settings = Settings()
