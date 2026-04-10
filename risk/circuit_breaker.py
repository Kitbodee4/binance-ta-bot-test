"""Circuit breaker: flash crash protection, gap risk, slippage guard."""

import time
from typing import List

from loguru import logger


class CircuitBreaker:
    """Protects against flash crashes and abnormal market conditions."""

    def __init__(
        self,
        flash_crash_pct: float = 0.05,
        halt_duration_min: int = 60,
        max_slippage_pct: float = 0.001,
        gap_multiplier: float = 1.5,
    ):
        self.flash_crash_pct = flash_crash_pct
        self.halt_duration_min = halt_duration_min
        self.max_slippage_pct = max_slippage_pct
        self.gap_multiplier = gap_multiplier
        self._halt_until: float | None = None

    def check_flash_crash(
        self,
        entry_price: float,
        current_price: float,
        side: str,
        threshold_pct: float | None = None,
    ) -> bool:
        """Check if flash crash conditions exist.

        Returns True when price has moved against the position by more
        than *threshold_pct* (default: ``flash_crash_pct``).
        """
        if entry_price <= 0:
            return False

        threshold = threshold_pct if threshold_pct is not None else self.flash_crash_pct

        if side == "long":
            pct_change = (entry_price - current_price) / entry_price
        else:
            pct_change = (current_price - entry_price) / entry_price

        return pct_change > threshold

    def check_slippage(
        self,
        intended_price: float,
        actual_price: float,
        side: str = "buy",
    ) -> bool:
        """Return True if slippage is within acceptable limits.

        Slippage is measured as the absolute percentage deviation of the
        actual fill price from the intended price.
        """
        if intended_price <= 0:
            return True

        abs_slippage_pct = abs(actual_price - intended_price) / intended_price
        return abs_slippage_pct <= self.max_slippage_pct

    def adjust_for_gap_risk(self, sl_distance_pct: float) -> float:
        """Return SL distance adjusted by ``gap_multiplier``."""
        return sl_distance_pct * self.gap_multiplier

    def trigger_halt(self) -> None:
        """Halt trading for ``halt_duration_min`` minutes."""
        self._halt_until = time.time() + self.halt_duration_min * 60
        logger.warning(
            f"Trading halted for {self.halt_duration_min} minutes"
        )

    def should_halt(self) -> bool:
        """Check if trading is currently halted."""
        if self._halt_until is None:
            return False
        if time.time() >= self._halt_until:
            self._halt_until = None
            logger.info("Halt period expired – trading resumed")
            return False
        return True


def check_directional_exposure(
    positions: list[dict],
    equity: float,
    max_pct: float = 0.6,
) -> bool:
    """Return True when net directional exposure is within *max_pct* of equity."""
    if equity <= 0:
        return False

    long_notional = sum(p["notional"] for p in positions if p["side"] == "long")
    short_notional = sum(p["notional"] for p in positions if p["side"] == "short")
    net_exposure = abs(long_notional - short_notional)

    return (net_exposure / equity) <= max_pct


def should_pause_trading(
    consecutive_losses: int,
    pause_at: int = 3,
    halt_at: int = 5,
) -> str:
    """Return one of ``"ok"``, ``"pause"``, or ``"halt"``."""
    if consecutive_losses >= halt_at:
        return "halt"
    if consecutive_losses >= pause_at:
        return "pause"
    return "ok"
