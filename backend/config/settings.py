from pydantic import BaseModel
from typing import Dict
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class MarketConfig(BaseModel):
    market: str
    min_commission: float
    commission_rate: float
    exchange_rate: float
    min_order_quantity: int = 1
    lot_size: int = 1


class HyperliquidBuilderConfig(BaseModel):
    """Hyperliquid Builder Fee Configuration"""
    builder_address: str
    builder_fee: int  # Fee in tenths of basis point (30 = 0.03%)


#  default configs for CRYPTO markets
DEFAULT_TRADING_CONFIGS: Dict[str, MarketConfig] = {
    "CRYPTO": MarketConfig(
        market="CRYPTO",
        min_commission=0.1,  # $0.1 minimum commission for crypto
        commission_rate=0.001,  # 0.1% commission rate (typical for crypto)
        exchange_rate=1.0,  # USD base
        min_order_quantity=1,  # Can trade fractional amounts
        lot_size=1,
    ),
}

# Hyperliquid Builder Fee Configuration
HYPERLIQUID_BUILDER_CONFIG = HyperliquidBuilderConfig(
    builder_address=os.getenv(
        "HYPERLIQUID_BUILDER_ADDRESS",
        "0x012E82f81e506b8f0EF69FF719a6AC65822b5924"
    ),
    builder_fee=int(os.getenv("HYPERLIQUID_BUILDER_FEE", "30"))  # 0.03% default
)


class BinanceBrokerConfig(BaseModel):
    """Binance Broker Configuration for fee rebates"""
    broker_id: str  # Broker ID for fee rebates


def _get_runtime_profile() -> str:
    raw = os.getenv("APP_RUNTIME_PROFILE", "full").strip().lower()
    return raw if raw in {"api", "factor", "full"} else "full"


# Binance Broker Configuration (optional, for fee rebates)
BINANCE_BROKER_CONFIG = BinanceBrokerConfig(
    broker_id=os.getenv("BINANCE_BROKER_ID", "")  # Empty if not a broker
)

# Runtime startup profile
APP_RUNTIME_PROFILE = _get_runtime_profile()
BACKGROUND_SERVICES_ENABLED = APP_RUNTIME_PROFILE in {"factor", "full"}
FACTOR_RUNTIME_ENABLED = APP_RUNTIME_PROFILE in {"factor", "full"}
BINANCE_RUNTIME_ENABLED = APP_RUNTIME_PROFILE == "full"
BOT_RUNTIME_ENABLED = APP_RUNTIME_PROFILE == "full"
FRONTEND_WATCHER_ENABLED = _env_bool("FRONTEND_WATCHER_ENABLED", False)

# Binance Daily Quota for non-rebate mainnet accounts
# This limits the number of AI-executed trades per day to prevent excessive API usage
BINANCE_DAILY_QUOTA_LIMIT = 40

# Factor Engine toggle (set to "true" to enable factor computation)
FACTOR_ENGINE_ENABLED = os.getenv("FACTOR_ENGINE_ENABLED", "false").lower() == "true"

# Automated factor research loop
FACTOR_RESEARCH_ENABLED = os.getenv("FACTOR_RESEARCH_ENABLED", "false").lower() == "true"
FACTOR_RESEARCH_INTERVAL_SECONDS = _env_int("FACTOR_RESEARCH_INTERVAL_SECONDS", 6 * 3600)
FACTOR_RESEARCH_EXCHANGE = os.getenv("FACTOR_RESEARCH_EXCHANGE", "hyperliquid")
FACTOR_RESEARCH_TOP_N_SYMBOLS = _env_int("FACTOR_RESEARCH_TOP_N_SYMBOLS", 20)
FACTOR_RESEARCH_LOOKBACK_DAYS = _env_int("FACTOR_RESEARCH_LOOKBACK_DAYS", 180)
FACTOR_RESEARCH_OBJECTIVE = os.getenv("FACTOR_RESEARCH_OBJECTIVE", "return_over_drawdown")
FACTOR_RESEARCH_FACTOR_SCOPE = os.getenv("FACTOR_RESEARCH_FACTOR_SCOPE", "builtin_only")
FACTOR_RESEARCH_PERIOD = os.getenv("FACTOR_RESEARCH_PERIOD", "1h")
FACTOR_RESEARCH_PRESCREEN_LIMIT = _env_int("FACTOR_RESEARCH_PRESCREEN_LIMIT", 10)
FACTOR_RESEARCH_RUN_ON_STARTUP = (
    os.getenv("FACTOR_RESEARCH_RUN_ON_STARTUP", "false").lower() == "true"
)
FACTOR_RESEARCH_AUTO_PROMOTE_PAPER = (
    os.getenv("FACTOR_RESEARCH_AUTO_PROMOTE_PAPER", "false").lower() == "true"
)
FACTOR_RESEARCH_PAPER_ACCOUNT_ID = _env_int("FACTOR_RESEARCH_PAPER_ACCOUNT_ID", 0)
FACTOR_RESEARCH_AUTO_PROMOTE_LIVE = (
    os.getenv("FACTOR_RESEARCH_AUTO_PROMOTE_LIVE", "false").lower() == "true"
)
FACTOR_RESEARCH_LIVE_ACCOUNT_ID = _env_int("FACTOR_RESEARCH_LIVE_ACCOUNT_ID", 0)
FACTOR_RESEARCH_LIVE_MIN_OBSERVATION_HOURS = _env_float(
    "FACTOR_RESEARCH_LIVE_MIN_OBSERVATION_HOURS",
    24.0,
)
FACTOR_RESEARCH_LIVE_MIN_TRADES = _env_int("FACTOR_RESEARCH_LIVE_MIN_TRADES", 10)
FACTOR_RESEARCH_LIVE_MIN_NET_PNL = _env_float("FACTOR_RESEARCH_LIVE_MIN_NET_PNL", 0.0)
FACTOR_RESEARCH_LIVE_MIN_WIN_RATE = _env_float("FACTOR_RESEARCH_LIVE_MIN_WIN_RATE", 50.0)
FACTOR_RESEARCH_LIVE_MAX_DRAWDOWN_PERCENT = _env_float(
    "FACTOR_RESEARCH_LIVE_MAX_DRAWDOWN_PERCENT",
    20.0,
)
FACTOR_RESEARCH_REQUIRE_LIVE_CONFIRM = (
    os.getenv("FACTOR_RESEARCH_REQUIRE_LIVE_CONFIRM", "true").lower() == "true"
)
