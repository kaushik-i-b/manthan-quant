"""Environment-backed configuration.

Risk percentages are initial defaults, not optimised competition parameters.
Venue payload schemas are intentionally absent until the official documents
are available. Live order submission stays disarmed.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    trading_api_url: str = "http://192.168.65.157:3002/api/v1"
    kafka_bootstrap_servers: str = "192.168.65.157:9094"
    kafka_enabled: bool = False
    # Official consumer-group naming was not in the repository. Leave blank
    # until it is copied from the problem statement. Kafka will not start
    # while this is empty.
    kafka_group_id: str = ""
    kafka_topic_ticks: str = "market.ticks"
    kafka_topic_news: str = "market.news"
    bot_access_token: str = ""
    dry_run: bool = True
    trading_enabled: bool = False
    # Must equal this exact phrase before any venue order POST is attempted.
    confirm_live_trading: str = ""
    live_confirm_phrase: str = "I_UNDERSTAND"

    max_position_pct: float = 0.10
    min_cash_reserve_pct: float = 0.20
    max_drawdown_pct: float = 0.08
    max_invested_pct: float = 0.80
    max_orders_per_day: int = 16
    max_outstanding_orders: int = 8
    initial_capital: float = 1_000_000.0
    entry_threshold: float = 0.45
    exit_threshold: float = 0.05
    cooldown_days: int = 4
    stop_loss_pct: float = 0.04
    take_profit_pct: float = 0.08
    risk_per_trade_pct: float = 0.004

    # Unverified against the simulator. 100% collateral and a 5-day square-off
    # are local safety defaults, not documented competition rules.
    short_collateral_pct: float = 1.0
    short_max_hold_days: int = 5
    shorts_enabled: bool = True

    # zero | synthetic_demo | configured
    # synthetic_demo uses a flat fictional fee so the desk can show costs.
    # It is not the competition schedule.
    cost_model: str = "synthetic_demo"
    synthetic_brokerage_inr: float = 15.0
    configured_brokerage_pct: float = 0.0
    configured_flat_fee_inr: float = 0.0
    configured_tax_pct: float = 0.0
    configured_dp_charge_inr: float = 0.0

    sim_day_seconds: float = 2.5
    news_delay_ms: int = 150
    heartbeat_interval_sec: float = 15.0
    stale_feed_multiplier: float = 3.0
    api_rate_limit_per_min: int = 120
    api_timeout_sec: float = 5.0

    host: str = "0.0.0.0"
    port: int = 8741
    market_mode: str = "mock"  # mock | kafka | venue
    replay_mode: str = "realtime"  # realtime | instant
    synthetic_seed: int = 42
    synthetic_days: int = 160
    warmup_days: int = 71
    demo_reject_day: int = 78
    demo_probe: bool = True
    control_token: str = "dev-control-token"
    database_path: str = ""
    log_level: str = "INFO"

    # Optional explicit venue field maps. Without these, venue payloads are
    # rejected rather than guessed.
    venue_stocks_map_path: str = ""
    venue_history_map_path: str = ""
    venue_tick_map_path: str = ""
    venue_news_map_path: str = ""
    venue_order_template_path: str = ""
    venue_heartbeat_template_path: str = ""
    venue_stage_stage_field: str = ""
    venue_stage_active_value: str = ""
    # Without these, a venue HTTP 200 is UNKNOWN and the ticker is frozen.
    venue_order_status_field: str = ""
    venue_order_status_value: str = ""

    @property
    def db_path(self) -> Path:
        if self.database_path:
            return Path(self.database_path)
        return BACKEND_ROOT / "data" / "manthan.db"

    def live_submission_armed(self) -> bool:
        return (
            self.market_mode == "venue"
            and not self.dry_run
            and self.trading_enabled
            and self.confirm_live_trading == self.live_confirm_phrase
            and bool(self.bot_access_token.strip())
            and bool(self.venue_order_template_path.strip())
        )


def get_settings() -> Settings:
    return Settings()
