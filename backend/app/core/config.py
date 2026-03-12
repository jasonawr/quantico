from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Jason Capital"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    binance_rest_url: str = "https://api.binance.com"
    default_symbol: str = "BTCUSDT"
    default_interval: str = "1m"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
