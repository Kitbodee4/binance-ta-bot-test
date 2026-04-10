"""BotEngine - Main state machine coordinator for Binance TA Bot.

Orchestrates scanning, signal evaluation, risk checking, order execution,
and position management through a state machine.

States: IDLE -> SCANNING -> SIGNAL_DETECTED -> RISK_CHECK -> EXECUTING
        -> MANAGING -> EXITING -> IDLE
"""

import time
import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from newtrade.binance_ta_bot.utils.trade_log import (
    init_trade_log,
    log_entry,
    log_exit,
)


class BotEngine:
    """Main bot engine coordinating all subsystems via a state machine.

    The engine runs a tick-based loop where each tick can advance through
    multiple states: scan -> evaluate -> risk check -> execute -> manage.
    """

    def __init__(
        self,
        exchange_client: Any,
        pair_scanner: Any,
        strategy: Any,
        risk_manager: Any,
        order_executor: Any,
        state_manager: Any,
        circuit_breaker: Any,
        config: Dict[str, Any],
        liquidation_guard: Any = None,
    ) -> None:
        self.exchange_client = exchange_client
        self.pair_scanner = pair_scanner
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.order_executor = order_executor
        self.state_manager = state_manager
        self.circuit_breaker = circuit_breaker
        self.config = config
        self.liquidation_guard = liquidation_guard

        self.scan_interval_sec: int = config.get("scan_interval_sec", 60)

        self._state: str = "IDLE"
        self._running: bool = False
        self._retry_count: int = 0
        self._positions: List[Dict[str, Any]] = []
        self._recent_loss_symbols: Dict[str, float] = {}

        # Risk tracking state
        self._equity: float = config.get("initial_equity", 1000.0)
        self._daily_pnl: float = 0.0
        self._weekly_pnl: float = 0.0
        self._consecutive_losses: int = 0

        # Load persisted state
        state = self.state_manager.load()
        if state:
            self._equity = state.get("equity", 0.0)
            if self._equity == 0.0:
                self._equity = config.get("initial_equity", 1000.0)
            self._daily_pnl = state.get("daily_pnl", 0.0)
            self._positions = state.get("open_positions", [])

    # -- Public API -------------------------------------------------------

    def get_state(self) -> str:
        return self._state

    def run(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("BotEngine started")
        try:
            while self._running:
                try:
                    self._tick()
                except Exception:
                    logger.exception("Unhandled error in tick loop")
                    self._state = "IDLE"
                if self._running:
                    time.sleep(self.scan_interval_sec)
        finally:
            self._running = False
            logger.info("BotEngine stopped")

    def stop(self) -> None:
        self._running = False

    # -- Internal methods --------------------------------------------------

    def _maybe_reset_daily(self) -> None:
        today = datetime.date.today().isoformat()
        last_reset = self.config.get("_last_daily_reset", "")
        if today != last_reset:
            self._daily_pnl = 0.0
            self.state_manager.reset_daily_stats()
            self.config["_last_daily_reset"] = today
            logger.info("Daily stats reset")

    def _tick(self) -> None:
        self._maybe_reset_daily()

        if self._positions:
            self._manage_positions()

        if self.circuit_breaker.should_halt():
            logger.warning("Circuit breaker halted - skipping scan")
            self._state = "IDLE"
            return

        while True:
            if self._state == "IDLE":
                try:
                    self._pending_pairs = self._scan()
                except Exception as e:
                    logger.error(f"Scan error: {e}")
                    self._state = "IDLE"
                    return
                if not self._pending_pairs:
                    self._state = "IDLE"
                    return
                self._state = "SCANNING"

            elif self._state == "SCANNING":
                pairs = getattr(self, "_pending_pairs", [])
                open_symbols = {p["symbol"] for p in self._positions}
                signal = None
                for symbol in pairs:
                    if symbol in open_symbols:
                        continue
                    try:
                        result = self._evaluate(symbol)
                        if result.get("signal", "none") not in (
                            "none", None, ""
                        ):
                            self._state = "SIGNAL_DETECTED"
                            result["symbol"] = symbol
                            signal = result
                            break
                    except Exception as e:
                        logger.error(f"Evaluate error for {symbol}: {e}")
                if signal is None:
                    self._state = "IDLE"
                    return
                self._pending_signal = signal

            elif self._state == "SIGNAL_DETECTED":
                self._state = "RISK_CHECK"

            elif self._state == "RISK_CHECK":
                signal = getattr(self, "_pending_signal", {})
                try:
                    risk_result = self._check_risk(signal)
                except Exception as e:
                    logger.error(f"Risk check error: {e}")
                    self._state = "IDLE"
                    return
                if not risk_result.get("approved", False):
                    logger.warning(
                        f"Risk rejected: "
                        f"{risk_result.get('reason', 'unknown')}"
                    )
                    self._state = "IDLE"
                    return
                self._state = "EXECUTING"

            elif self._state == "EXECUTING":
                signal = getattr(self, "_pending_signal", {})
                try:
                    order_result = self._execute(signal)
                except Exception as e:
                    logger.error(f"Execute error: {e}")
                    self._retry_count += 1
                    self._state = "IDLE"
                    return
                if order_result.get("status") in ("filled", "closed"):
                    position = {
                        "symbol": signal.get("symbol", ""),
                        "side": signal.get("signal", "long"),
                        "size": order_result.get(
                            "filled", signal.get("size", 0)
                        ),
                        "entry_price": order_result.get(
                            "avg_price", signal.get("entry_price", 0)
                        ),
                        "stop_loss": signal.get("stop_loss", 0),
                        "take_profit": signal.get("take_profit", 0),
                    }
                    self._on_position_opened(position)
                    self._state = "IDLE"
                    return
                else:
                    logger.warning(f"Order not filled: {order_result}")
                    self._retry_count += 1
                    self._state = "IDLE"
                    return

            else:
                self._state = "IDLE"
                return

    def _scan(self) -> List[str]:
        return self.pair_scanner.scan()

    def _evaluate(self, symbol: str) -> Dict[str, Any]:
        # ── cooldown หลัง SL ──
        last_loss = self._recent_loss_symbols.get(symbol, 0)
        if time.time() - last_loss < 7200:
            logger.info(f"{symbol} skipped: cooldown after loss")
            return {
                "signal": "none",
                "trend": "unknown",
                "htf_trend": "unknown",
                "ema_signal": "none",
                "rsi_ok": False,
                "volume_ok": False,
            }

        candles_entry = self.exchange_client.fetch_ohlcv(
            symbol,
            timeframe=self.strategy.entry_tf,
            limit=self.strategy.entry_limit,
        )
        candles_trend = self.exchange_client.fetch_ohlcv(
            symbol,
            timeframe=self.strategy.trend_tf,
            limit=self.strategy.trend_limit,
        )
        candles_htf = self.exchange_client.fetch_ohlcv(
            symbol,
            timeframe=self.strategy.htf_tf,
            limit=self.strategy.htf_limit,
        )
        if candles_entry:
            last_vol = candles_entry[-1][5]
            if last_vol == 0:
                logger.info(
                    f"{symbol} skipped: zero volume on "
                    f"{self.strategy.entry_tf}"
                )
                return {
                    "signal": "none",
                    "trend": "unknown",
                    "htf_trend": "unknown",
                    "ema_signal": "none",
                    "rsi_ok": False,
                    "volume_ok": False,
                }

        return self.strategy.evaluate(
            candles_entry, candles_trend, candles_htf, pair=symbol
        )

    def _check_risk(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        return self.risk_manager.check_all_limits(
            self._equity,
            self._daily_pnl,
            self._weekly_pnl,
            self._positions,
            self._consecutive_losses,
            self.exchange_client,
            signal.get("symbol", ""),
        )

    def _side_to_order(self, side: str) -> str:
        if side == "long":
            return "buy"
        if side == "short":
            return "sell"
        raise ValueError(f"Unknown side: {side!r}")

    def _execute(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        symbol = signal.get("symbol", "")
        side = signal.get("signal", "long")

        ticker = self.exchange_client.fetch_ticker(symbol)
        entry_price = ticker["last"]

        stop_loss = signal.get("stop_loss", 0)
        take_profit = signal.get("take_profit", 0)

        if not stop_loss or not take_profit:
            sl_tp = self.risk_manager.calculate_sl_tp(
                entry_price=entry_price,
                side=side,
                swing_low=entry_price * 0.98,
                swing_high=entry_price * 1.02,
            )
            stop_loss = sl_tp["stop_loss"]
            take_profit = sl_tp["take_profit"]

        signal["stop_loss"] = stop_loss
        signal["take_profit"] = take_profit

        if stop_loss > 0 and entry_price > 0:
            size = self.risk_manager.calculate_position_size(
                self._equity, entry_price, stop_loss
            )
        else:
            size = signal.get("size", 0)

        order_side = self._side_to_order(side)

        return self.order_executor.execute_entry(
            symbol=symbol,
            side=order_side,
            size=size,
            intended_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def _manage_positions(self) -> None:
        for position in list(self._positions):
            symbol = position["symbol"]
            try:
                ticker = self.exchange_client.fetch_ticker(symbol)
            except Exception as e:
                logger.error(f"Ticker fetch error for {symbol}: {e}")
                continue
            current_price = ticker["last"]
            side = position.get("side", "long")
            entry_price = position.get("entry_price", 0)

            # Flash crash check
            if self.circuit_breaker.check_flash_crash(
                entry_price=entry_price,
                current_price=current_price,
                side=side,
            ):
                logger.warning(f"Flash crash detected on {symbol}!")
                self.circuit_breaker.trigger_halt()
                for pos in list(self._positions):
                    self._exit_position(pos, reason="flash_crash")
                return

            # Liquidation guard check
            liq_price = position.get("liquidation_price", 0)
            if self.liquidation_guard is not None and liq_price > 0:
                guard_result = self.liquidation_guard.check(
                    side=side,
                    entry_price=entry_price,
                    current_price=current_price,
                    liquidation_price=liq_price,
                )
                if guard_result.get("action") == "close":
                    logger.warning(
                        f"Liquidation risk on {symbol}: "
                        f"{guard_result.get('distance_pct', 0):.1%}"
                    )
                    self._exit_position(
                        position, reason="liquidation_risk"
                    )
                    continue

            stop_loss = position.get("stop_loss", 0)
            take_profit = position.get("take_profit", 0)

            if side == "long":
                sl_hit = (
                    current_price <= stop_loss and stop_loss > 0
                )
                tp_hit = (
                    current_price >= take_profit and take_profit > 0
                )
            else:
                sl_hit = (
                    current_price >= stop_loss and stop_loss > 0
                )
                tp_hit = (
                    current_price <= take_profit and take_profit > 0
                )

            if sl_hit:
                logger.info(
                    f"SL hit for {symbol} at {current_price}"
                )
                self._exit_position(position, reason="sl_hit")
                continue
            elif tp_hit:
                logger.info(
                    f"TP hit for {symbol} at {current_price}"
                )
                self._exit_position(position, reason="tp_hit")
                continue

    def _exit_position(
        self, position: Dict[str, Any], reason: str = ""
    ) -> None:
        symbol = position["symbol"]
        logger.info(f"Exiting {symbol} reason={reason}")

        pos_side = position.get("side", "long")
        ticker = self.exchange_client.fetch_ticker(symbol)
        close_price = ticker["last"]
        entry_price = position.get("entry_price", 0)
        size = position.get("size", 0)

        self.order_executor.close_position(
            symbol=symbol,
            side=pos_side,
            size=size,
        )

        # ── คำนวณ PnL ──
        if pos_side == "long":
            pnl = (close_price - entry_price) * size
        else:
            pnl = (entry_price - close_price) * size
        self._daily_pnl += pnl
        self._weekly_pnl += pnl

        # ── track consecutive losses + cooldown ──
        if pnl < 0 and reason == "sl_hit":
            self._recent_loss_symbols[symbol] = time.time()
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        log_exit(
            symbol=symbol,
            side=pos_side,
            entry_price=entry_price,
            close_price=close_price,
            size=size,
            stop_loss=position["stop_loss"],
            take_profit=position["take_profit"],
            reason=reason,
        )

        if position in self._positions:
            self._positions.remove(position)

        self.state_manager.update_full_state(
            equity=self._equity,
            daily_pnl=self._daily_pnl,
            positions=self._positions,
        )

        self._state = "MANAGING" if self._positions else "IDLE"

    def _on_position_opened(self, position: Dict[str, Any]) -> None:
        # ── เช็ค duplicate ──
        for existing in self._positions:
            if existing["symbol"] == position["symbol"]:
                logger.info(
                    f"Duplicate skipped: {position['symbol']}"
                )
                return

        self._positions.append(position)
        self.state_manager.update_full_state(
            equity=self._equity,
            daily_pnl=self._daily_pnl,
            positions=self._positions,
        )
        log_entry(
            symbol=position["symbol"],
            side=position["side"],
            entry_price=position["entry_price"],
            size=position["size"],
            stop_loss=position["stop_loss"],
            take_profit=position["take_profit"],
        )
