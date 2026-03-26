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

    enable_scalping: bool = True
    enable_swing: bool = True
    enable_news: bool = True

    tick_interval_seconds: int = 3
    heartbeat_seconds: int = 60


settings = Settings()
