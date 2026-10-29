"""Central configuration. All venue details configurable; safe defaults for local dev."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "MANTHAN QUANT"
    TRADING_API_URL: str = "http://192.168.65.157:3002/api/v1"
    KAFKA_BOOTSTRAP_SERVERS: str = "192.168.65.157:9094"
    KAFKA_TOPIC_TICKS: str = "market.ticks"
    KAFKA_TOPIC_NEWS: str = "market.news"
    KAFKA_GROUP_ID: str = "manthan-quant-bot-v1"
    BOT_ACCESS_TOKEN: str = ""
    DRY_RUN: bool = True
    TRADING_ENABLED: bool = False
    MAX_POSITION_PCT: float = 0.10
    MAX_CONCENTRATION_PCT: float = 0.25
    MAX_INVESTED_PCT: float = 0.80
    MIN_CASH_RESERVE_PCT: float = 0.20
    MAX_DRAWDOWN_PCT: float = 0.08
    MAX_ORDERS_PER_DAY: int = 20
    MAX_OUTSTANDING_ORDERS: int = 5
    BROKERAGE_PCT: float = 0.0005
    DP_CHARGE: float = 15.0
    STT_PCT: float = 0.001
    STARTING_CAPITAL: float = 1_000_000.0
    API_RATE_LIMIT_PER_MIN: int = 110
    HEARTBEAT_INTERVAL_SEC: float = 10.0
    MOCK_MODE: bool = True
    SIM_TICK_INTERVAL_SEC: float = 1.0
    DB_PATH: str = "manthan_quant.db"


settings = Settings()
