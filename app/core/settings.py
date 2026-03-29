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
    min_balance_protection: float = 0.0
    cooldown_after_losses: int = 0

    default_symbol: str = "EURUSD"

    enable_smc_ict: bool = True
    enable_scalper: bool = True
    enable_news: bool = True
    enable_adaptive_weighting: bool = True
    enable_london_ny_session: bool = True
    enable_sr_fvg: bool = True

    bridge_api_base: str = ""
    bridge_token: str = ""

    dexter_enabled: bool = False
    dexter_base_url: str = "http://dexter-service:8081"
    dexter_timeout_seconds: int = 45

    trading_agents_enabled: bool = False
    trading_agents_base_url: str = "http://tradingagents-service:8082"
    trading_agents_timeout_seconds: int = 60

    consensus_min_confidence: float = 0.75

    auto_trading_enabled: bool = False
    auto_default_symbol: str = "XAUUSD.m"
    auto_default_lot: float = 0.01
    risk_mode: str = "normal"  # safe|normal|aggressive
    strict_point_value_validation: bool = True
    paper_valuation_policy: str = "warn"  # warn|block
    auto_cooldown_seconds: int = 120
    report_interval_seconds: int = 3600
    watch_symbols: str = "XAUUSD.m,BRENT.m"
    daily_drawdown_limit_pct: float = 6.0
    daily_profit_target_pct: float = 3.0

    ict_killzones_enabled: bool = True
    ict_london_killzone_utc: str = "07:00-10:00"
    ict_newyork_killzone_utc: str = "12:00-15:00"

    tick_interval_seconds: int = 3
    heartbeat_seconds: int = 60


settings = Settings()
