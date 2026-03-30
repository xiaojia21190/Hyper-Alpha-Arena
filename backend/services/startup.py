"""Application startup initialization service"""

import logging
import threading

from services.scheduler import start_scheduler, setup_market_tasks, task_scheduler
from services.market_stream import start_market_stream, stop_market_stream
from services.market_events import subscribe_price_updates, unsubscribe_price_updates
from services.trading_strategy import start_strategy_manager, stop_strategy_manager
from services.hyperliquid_symbol_service import (
    refresh_hyperliquid_symbols,
    schedule_symbol_refresh_task,
    build_market_stream_symbols,
)

logger = logging.getLogger(__name__)


def _program_price_update_handler(event: dict) -> None:
    """Convert market event payload for ProgramExecutionService."""
    symbol = event.get("symbol")
    price = event.get("price")
    event_time = event.get("event_time")
    if symbol and price:
        from services.program_execution_service import program_execution_service

        program_execution_service.on_price_update(symbol, float(price), event_time)


def _strategy_price_update_handler(event: dict) -> None:
    """Convert market event payload for strategy manager."""
    symbol = event.get("symbol")
    price = event.get("price")
    event_time = event.get("event_time")
    if symbol and price:
        from services.trading_strategy import handle_price_update as strategy_price_update

        strategy_price_update(symbol, float(price), event_time)


def _start_scheduler_services() -> None:
    print("Starting scheduler...")
    start_scheduler()
    print("Scheduler started")
    logger.info("Scheduler service started")

    refresh_hyperliquid_symbols()
    schedule_symbol_refresh_task()

    setup_market_tasks()
    logger.info("Market scheduled tasks have been set up")

    from services.price_cache import clear_expired_prices

    task_scheduler.add_interval_task(
        task_func=clear_expired_prices,
        interval_seconds=120,
        task_id="price_cache_cleanup",
    )
    logger.info("Price cache cleanup task started (2-minute interval)")


def _start_hyperliquid_factor_market_services() -> None:
    import asyncio

    combined_symbols = build_market_stream_symbols()
    from database.connection import SessionLocal
    from database.models import GlobalSamplingConfig

    with SessionLocal() as db:
        global_config = db.query(GlobalSamplingConfig).first()
        stream_interval = max(5, global_config.sampling_interval if global_config else 18)

    print(f"Starting market data stream (interval={stream_interval}s)...")
    start_market_stream(combined_symbols, interval_seconds=stream_interval)
    print("Market data stream started")
    logger.info("Market data stream initialized")

    from services.hyperliquid_snapshot_service import hyperliquid_snapshot_service
    from services.kline_realtime_collector import realtime_collector
    from services.market_flow_collector import (
        cleanup_old_market_flow_data,
        market_flow_collector,
    )

    asyncio.create_task(hyperliquid_snapshot_service.start())
    logger.info("Hyperliquid snapshot service started (30-second interval)")

    asyncio.create_task(realtime_collector.start())
    logger.info("K-line realtime collection service started (1-minute interval)")

    print("Starting market flow collector...")
    market_flow_collector.start()
    print("Market flow collector started")
    logger.info("Market flow collector started (15-second aggregation)")

    task_scheduler.add_interval_task(
        task_func=cleanup_old_market_flow_data,
        interval_seconds=6 * 3600,
        task_id="market_flow_data_cleanup",
    )
    logger.info("Market flow data cleanup task started (6-hour interval, 30-day retention)")


def _start_factor_services() -> None:
    from config.settings import (
        FACTOR_ENGINE_ENABLED,
        FACTOR_RESEARCH_AUTO_PROMOTE_LIVE,
        FACTOR_RESEARCH_AUTO_PROMOTE_PAPER,
        FACTOR_RESEARCH_ENABLED,
        FACTOR_RESEARCH_EXCHANGE,
        FACTOR_RESEARCH_FACTOR_SCOPE,
        FACTOR_RESEARCH_INTERVAL_SECONDS,
        FACTOR_RESEARCH_LIVE_ACCOUNT_ID,
        FACTOR_RESEARCH_LIVE_MAX_DRAWDOWN_PERCENT,
        FACTOR_RESEARCH_LIVE_MIN_NET_PNL,
        FACTOR_RESEARCH_LIVE_MIN_OBSERVATION_HOURS,
        FACTOR_RESEARCH_LIVE_MIN_TRADES,
        FACTOR_RESEARCH_LIVE_MIN_WIN_RATE,
        FACTOR_RESEARCH_LOOKBACK_DAYS,
        FACTOR_RESEARCH_OBJECTIVE,
        FACTOR_RESEARCH_PAPER_ACCOUNT_ID,
        FACTOR_RESEARCH_PERIOD,
        FACTOR_RESEARCH_PRESCREEN_LIMIT,
        FACTOR_RESEARCH_REQUIRE_LIVE_CONFIRM,
        FACTOR_RESEARCH_RUN_ON_STARTUP,
        FACTOR_RESEARCH_TOP_N_SYMBOLS,
    )

    if FACTOR_ENGINE_ENABLED:
        from services.factor_computation_service import factor_computation_service
        from services.factor_effectiveness_service import factor_effectiveness_service

        factor_computation_service.start()
        factor_effectiveness_service.start()
        logger.info("[FactorEngine] Factor computation + effectiveness services started")
    else:
        print("[FactorEngine] Disabled (set FACTOR_ENGINE_ENABLED=true to enable)")

    if FACTOR_RESEARCH_ENABLED:
        from services.factor_research_service import factor_research_automation_service

        factor_research_automation_service.start(
            interval_seconds=FACTOR_RESEARCH_INTERVAL_SECONDS,
            exchange=FACTOR_RESEARCH_EXCHANGE,
            top_n_symbols=FACTOR_RESEARCH_TOP_N_SYMBOLS,
            lookback_days=FACTOR_RESEARCH_LOOKBACK_DAYS,
            objective=FACTOR_RESEARCH_OBJECTIVE,
            factor_scope=FACTOR_RESEARCH_FACTOR_SCOPE,
            period=FACTOR_RESEARCH_PERIOD,
            prescreen_limit=FACTOR_RESEARCH_PRESCREEN_LIMIT,
            run_immediately=FACTOR_RESEARCH_RUN_ON_STARTUP,
            auto_promote_paper=FACTOR_RESEARCH_AUTO_PROMOTE_PAPER,
            paper_account_id=FACTOR_RESEARCH_PAPER_ACCOUNT_ID,
            auto_promote_live=FACTOR_RESEARCH_AUTO_PROMOTE_LIVE,
            live_account_id=FACTOR_RESEARCH_LIVE_ACCOUNT_ID,
            live_min_observation_hours=FACTOR_RESEARCH_LIVE_MIN_OBSERVATION_HOURS,
            live_min_trades=FACTOR_RESEARCH_LIVE_MIN_TRADES,
            live_min_net_pnl=FACTOR_RESEARCH_LIVE_MIN_NET_PNL,
            live_min_win_rate=FACTOR_RESEARCH_LIVE_MIN_WIN_RATE,
            live_max_drawdown_percent=FACTOR_RESEARCH_LIVE_MAX_DRAWDOWN_PERCENT,
            require_live_confirm=FACTOR_RESEARCH_REQUIRE_LIVE_CONFIRM,
        )
        logger.info("[FactorResearch] Automated research loop started")
    else:
        print("[FactorResearch] Disabled (set FACTOR_RESEARCH_ENABLED=true to enable)")


def _start_program_execution_services() -> None:
    subscribe_price_updates(_program_price_update_handler)
    logger.info("Program execution service subscribed to price updates")


def _stop_program_execution_services() -> None:
    unsubscribe_price_updates(_program_price_update_handler)


def _start_binance_services() -> None:
    import asyncio

    from services.binance_symbol_service import (
        get_selected_symbols as get_binance_selected_symbols,
        refresh_binance_symbols,
        schedule_symbol_refresh_task as schedule_binance_symbol_refresh,
    )
    from services.binance_snapshot_service import binance_snapshot_service
    from services.exchanges.binance_collector import binance_collector
    from services.exchanges.binance_ws_collector import binance_ws_collector

    refresh_binance_symbols()
    schedule_binance_symbol_refresh()
    logger.info("[Binance] Symbol catalog refreshed and periodic refresh scheduled")

    asyncio.create_task(binance_snapshot_service.start())
    logger.info("Binance snapshot service started (5-minute interval)")

    binance_watchlist = get_binance_selected_symbols()
    print(f"Starting Binance data collector with Binance watchlist: {binance_watchlist}")
    symbols = binance_watchlist if binance_watchlist else ["BTC"]
    binance_collector.start(symbols=symbols)
    print("Binance data collector started")
    logger.info(f"[Binance] Data collector started with symbols: {binance_watchlist}")

    binance_ws_collector.start(symbols=symbols)
    print("Binance WebSocket collector started")
    logger.info(f"[Binance] WebSocket collector started with symbols: {binance_watchlist}")


def _stop_binance_services() -> None:
    from services.exchanges.binance_collector import binance_collector
    from services.exchanges.binance_ws_collector import binance_ws_collector

    binance_collector.stop()
    binance_ws_collector.stop()


def _start_bot_services() -> None:
    from services.scheduler import start_asset_curve_broadcast

    subscribe_price_updates(_strategy_price_update_handler)
    logger.info("Strategy manager subscribed to price updates")

    print("Starting strategy manager...")
    start_strategy_manager()
    print("Strategy manager started")

    start_asset_curve_broadcast()
    logger.info("Asset curve broadcast task started (60-second interval)")


def _stop_bot_services() -> None:
    unsubscribe_price_updates(_strategy_price_update_handler)
    stop_strategy_manager()


def _stop_hyperliquid_factor_market_services() -> None:
    import asyncio

    from services.hyperliquid_snapshot_service import hyperliquid_snapshot_service
    from services.kline_realtime_collector import realtime_collector
    from services.market_flow_collector import market_flow_collector

    stop_market_stream()
    hyperliquid_snapshot_service.stop()
    asyncio.create_task(realtime_collector.stop())
    market_flow_collector.stop()


def _stop_factor_services() -> None:
    from services.factor_research_service import factor_research_automation_service

    factor_research_automation_service.stop()


def initialize_services(profile: str = "full"):
    """Initialize services by runtime profile."""
    normalized_profile = (profile or "full").strip().lower()
    try:
        _start_scheduler_services()

        if normalized_profile in {"factor", "full"}:
            _start_hyperliquid_factor_market_services()
            _start_factor_services()
            _start_program_execution_services()

        if normalized_profile == "full":
            _start_binance_services()
            _start_bot_services()

        logger.info("All services initialized successfully")
    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        raise


def shutdown_services(profile: str = "full"):
    """Shut down services by runtime profile."""
    normalized_profile = (profile or "full").strip().lower()
    try:
        if normalized_profile == "full":
            _stop_bot_services()
            _stop_binance_services()

        if normalized_profile in {"factor", "full"}:
            _stop_program_execution_services()
            _stop_hyperliquid_factor_market_services()
            _stop_factor_services()

        from services.scheduler import stop_scheduler

        stop_scheduler()
        logger.info("All services have been shut down")
    except Exception as e:
        logger.error(f"Failed to shut down services: {e}")


def schedule_auto_trading(interval_seconds: int = 300, max_ratio: float = 0.2, use_ai: bool = True) -> None:
    """Schedule automatic trading tasks
    
    Args:
        interval_seconds: Interval between trading attempts
        max_ratio: Maximum portion of portfolio to use per trade
        use_ai: If True, use AI-driven trading; if False, use random trading
    """
    from services.auto_trader import (
        place_ai_driven_crypto_order,
        place_random_crypto_order,
        AUTO_TRADE_JOB_ID,
        AI_TRADE_JOB_ID
    )

    def execute_trade():
        try:
            if use_ai:
                place_ai_driven_crypto_order(max_ratio)
            else:
                place_random_crypto_order(max_ratio)
            logger.info("Initial auto-trading execution completed")
        except Exception as e:
            logger.error(f"Error during initial auto-trading execution: {e}")

    if use_ai:
        task_func = place_ai_driven_crypto_order
        job_id = AI_TRADE_JOB_ID
        logger.info("Scheduling AI-driven crypto trading")
    else:
        task_func = place_random_crypto_order
        job_id = AUTO_TRADE_JOB_ID
        logger.info("Scheduling random crypto trading")

    # Schedule the recurring task
    task_scheduler.add_interval_task(
        task_func=task_func,
        interval_seconds=interval_seconds,
        task_id=job_id,
        max_ratio=max_ratio,
    )
    
    # Execute the first trade immediately in a separate thread to avoid blocking
    initial_trade = threading.Thread(target=execute_trade, daemon=True)
    initial_trade.start()
