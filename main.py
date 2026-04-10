"""CLI entry point and bot lifecycle for Binance TA Bot.

Wires all modules together and manages the BotEngine run loop.

Usage:
    python -m binance_ta_bot                    # Execute (dry-run)
    python -m binance_ta_bot --mode execute     # Execute mode
    python -m binance_ta_bot --mode status      # Show state
    python -m binance_ta_bot --config path.yaml # Custom config
    python -m binance_ta_bot --verbose          # DEBUG logging
"""

import argparse
import os
import signal
import sys
from pathlib import Path

from loguru import logger

from binance_ta_bot.core.bot_engine import BotEngine
from binance_ta_bot.core.exchange_client import ExchangeClient
from binance_ta_bot.core.state_manager import StateManager
from binance_ta_bot.execution.order_executor import OrderExecutor
from binance_ta_bot.risk.circuit_breaker import CircuitBreaker
from binance_ta_bot.risk.liquidation_guard import LiquidationGuard
from binance_ta_bot.risk.risk_manager import RiskManager
from binance_ta_bot.scanner.pair_scanner import PairScanner
from binance_ta_bot.strategy.multi_tf_strategy import (
    MultiTimeframeStrategy,
)
from binance_ta_bot.utils.helpers import load_yaml_config
from binance_ta_bot.utils.logger import setup_logger
from binance_ta_bot.utils.trade_log import init_trade_log

DEFAULT_CONFIG = Path(__file__).parent / "config.yaml"
DEFAULT_STATE = "state_ta_bot.json"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="binance_ta_bot",
        description="Binance Perpetual Futures TA Trading Bot",
    )
    parser.add_argument(
        "--mode",
        choices=["execute", "status"],
        default="execute",
        help="Run mode (default: execute)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Paper-trade mode (overrides config)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(DEFAULT_CONFIG),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser.parse_args(argv)


def _build_bot(config: dict, dry_run: bool) -> BotEngine:
    """Wire all modules and return a ready BotEngine.

    Args:
        config: Parsed config dict from config.yaml.
        dry_run: Whether to run in paper-trade mode.

    Returns:
        Fully wired BotEngine instance.
    """
    # Read API keys from environment
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_SECRET", "")

    if not dry_run and (not api_key or not api_secret):
        logger.warning(
            "API keys not set – falling back to dry-run mode. "
            "Set BINANCE_API_KEY and BINANCE_SECRET env vars."
        )
        dry_run = True

    exchange_name = config.get("exchange", {}).get("name", "binanceusdm")

    # --- Core ---
    exchange_client = ExchangeClient(
        exchange_name=exchange_name,
        api_key=api_key,
        api_secret=api_secret,
        dry_run=dry_run,
    )

    state_file = config.get("bot", {}).get("state_file", DEFAULT_STATE)
    state_manager = StateManager(state_file=state_file)
    state_manager.load()

    # --- Scanner ---
    scanner_cfg = config.get("scanner", {})
    pair_scanner = PairScanner(
        exchange_client=exchange_client,
        top_n=scanner_cfg.get("top_n_pairs", 20),
        min_volume_usd=scanner_cfg.get("min_volume_usd", 10_000_000),
        exclude_patterns=scanner_cfg.get("exclude_patterns"),
    )

    # --- Strategy ---
    strat_cfg = config.get("strategy", {})
    strategy = MultiTimeframeStrategy(
        entry_tf=strat_cfg.get("entry_tf", "15m"),
        trend_tf=strat_cfg.get("trend_tf", "1h"),
        htf_tf=strat_cfg.get("htf_tf", "4h"),
        entry_limit=strat_cfg.get("entry_limit", 1000),
        trend_limit=strat_cfg.get("trend_limit", 1000),
        htf_limit=strat_cfg.get("htf_limit", 1000),
        ema_fast=strat_cfg.get("ema_fast", 9),
        ema_slow=strat_cfg.get("ema_slow", 21),
        rsi_period=strat_cfg.get("rsi_period", 14),
        rsi_overbought=strat_cfg.get("rsi_overbought", 70),
        rsi_oversold=strat_cfg.get("rsi_oversold", 30),
        volume_avg_period=strat_cfg.get("volume_avg_period", 20),
        volume_spike_mult=strat_cfg.get("volume_spike_mult", 1.5),
        htf_ema_fast=strat_cfg.get("htf_ema_fast", 50),
        htf_ema_slow=strat_cfg.get("htf_ema_slow", 200),
        htf_ranging_threshold_pct=strat_cfg.get(
            "htf_ranging_threshold_pct", 0.005
        ),
        regime_detection=strat_cfg.get("regime_detection", False),
        adx_period=strat_cfg.get("adx_period", 14),
        adx_threshold=strat_cfg.get("adx_threshold", 25),
        dynamic_timeframes=strat_cfg.get("dynamic_timeframes", False),
        volatility_lookback=strat_cfg.get("volatility_lookback", 14),
    )

    # --- Risk ---
    risk_cfg = config.get("risk", {})
    risk_manager = RiskManager(
        risk_per_trade=risk_cfg.get("risk_per_trade", 0.01),
        max_leverage=risk_cfg.get("max_leverage", 3),
        max_positions=risk_cfg.get("max_positions", 3),
        daily_loss_limit=risk_cfg.get("daily_loss_limit", 0.03),
        weekly_loss_limit=risk_cfg.get("weekly_loss_limit", 0.08),
        min_sl_pct=risk_cfg.get("min_sl_pct", 0.005),
        max_sl_pct=risk_cfg.get("max_sl_pct", 0.03),
        gap_multiplier=risk_cfg.get("gap_multiplier", 1.5),
        max_directional_exposure=risk_cfg.get(
            "max_directional_exposure", 0.6
        ),
        consecutive_loss_pause=risk_cfg.get("consecutive_loss_pause", 3),
        consecutive_loss_halt=risk_cfg.get("consecutive_loss_halt", 5),
    )

    cb_cfg = config.get("circuit_breaker", {})
    circuit_breaker = CircuitBreaker(
        flash_crash_pct=cb_cfg.get("flash_crash_pct", 0.05),
        halt_duration_min=cb_cfg.get("halt_duration_min", 60),
        max_slippage_pct=cb_cfg.get("max_slippage_pct", 0.001),
        gap_multiplier=risk_cfg.get("gap_multiplier", 1.5),
    )

    liquidation_guard = LiquidationGuard(
        close_threshold_pct=0.20,
        warn_threshold_pct=0.30,
    )

    # --- Execution ---
    order_executor = OrderExecutor(
        exchange_client=exchange_client,
        circuit_breaker=circuit_breaker,
        max_slippage_pct=cb_cfg.get("max_slippage_pct", 0.001),
        dry_run=dry_run,
    )

    # --- Engine ---
    bot_cfg = config.get("bot", {})
    engine_config = {
        "scan_interval_sec": bot_cfg.get("scan_interval_sec", 60),
        "dry_run": dry_run,
        "log_level": bot_cfg.get("log_level", "INFO"),
        "initial_equity": bot_cfg.get("initial_equity", 1000)

    }

    return BotEngine(
        exchange_client=exchange_client,
        pair_scanner=pair_scanner,
        strategy=strategy,
        risk_manager=risk_manager,
        order_executor=order_executor,
        state_manager=state_manager,
        circuit_breaker=circuit_breaker,
        config=engine_config,
        liquidation_guard=liquidation_guard,
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _parse_args(argv)

    # Logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logger(level=log_level)

    # Config
    config = load_yaml_config(args.config)
    init_trade_log()

    # Resolve dry-run: CLI flag overrides config
    if args.dry_run is not None:
        dry_run = args.dry_run
    else:
        dry_run = config.get("bot", {}).get("dry_run", True)

    logger.info(
        f"Binance TA Bot starting | mode={args.mode} "
        f"dry_run={dry_run} config={args.config}"
    )

    if args.mode == "status":
        state_manager = StateManager(
            state_file=config.get("bot", {}).get(
                "state_file", DEFAULT_STATE
            )
        )
        state = state_manager.load()
        logger.info(f"Bot state: {state}")
        return

    # Build and run bot
    bot = _build_bot(config, dry_run=dry_run)

    # Graceful shutdown on SIGINT / SIGTERM
    def _shutdown(signum, frame):
        logger.info(f"Received signal {signum}, stopping bot...")
        bot.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    bot.run()
