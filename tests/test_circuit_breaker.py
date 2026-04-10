"""Tests for circuit breaker: flash crash, slippage, gap risk, exposure."""

import time
from unittest.mock import patch

import pytest

from newtrade.binance_ta_bot.risk.circuit_breaker import (
    CircuitBreaker,
    check_directional_exposure,
    should_pause_trading,
)


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def cb():
    """Default circuit breaker instance."""
    return CircuitBreaker()


# ── check_flash_crash ────────────────────────────────────────────────


class TestFlashCrash:
    def test_long_price_drops_above_threshold(self, cb):
        """Long position with price drop >5% must trigger."""
        assert cb.check_flash_crash(
            entry_price=100.0, current_price=94.0, side="long",
        ) is True

    def test_long_price_drops_exactly_at_threshold(self, cb):
        """Exactly 5% drop should NOT trigger (must be strictly greater)."""
        assert cb.check_flash_crash(
            entry_price=100.0, current_price=95.0, side="long",
        ) is False

    def test_long_price_drops_below_threshold(self, cb):
        """Price drop within threshold should not trigger."""
        assert cb.check_flash_crash(
            entry_price=100.0, current_price=96.0, side="long",
        ) is False

    def test_long_price_rises(self, cb):
        """Price going up on long should not trigger."""
        assert cb.check_flash_crash(
            entry_price=100.0, current_price=110.0, side="long",
        ) is False

    def test_short_price_rises_above_threshold(self, cb):
        """Short position with price rise >5% must trigger."""
        assert cb.check_flash_crash(
            entry_price=100.0, current_price=106.0, side="short",
        ) is True

    def test_short_price_rises_exactly_at_threshold(self, cb):
        """Exactly 5% rise should NOT trigger."""
        assert cb.check_flash_crash(
            entry_price=100.0, current_price=105.0, side="short",
        ) is False

    def test_short_price_rises_below_threshold(self, cb):
        """Price rise within threshold should not trigger."""
        assert cb.check_flash_crash(
            entry_price=100.0, current_price=103.0, side="short",
        ) is False

    def test_short_price_drops(self, cb):
        """Price going down on short should not trigger."""
        assert cb.check_flash_crash(
            entry_price=100.0, current_price=90.0, side="short",
        ) is False

    def test_custom_threshold(self, cb):
        """Custom threshold should override default."""
        # 96.9 on 100 = 3.1% drop, exceeds custom 3% threshold
        assert cb.check_flash_crash(
            entry_price=100.0, current_price=96.9, side="long",
            threshold_pct=0.03,
        ) is True

    def test_zero_entry_price(self, cb):
        """Zero entry price should not crash, return False."""
        assert cb.check_flash_crash(
            entry_price=0.0, current_price=100.0, side="long",
        ) is False


# ── check_slippage ───────────────────────────────────────────────────


class TestSlippage:
    def test_buy_within_limit(self, cb):
        """Buy with slippage within 0.1% should pass."""
        # intended 100, actual 100.05 → 0.05% slippage
        assert cb.check_slippage(
            intended_price=100.0, actual_price=100.05, side="buy",
        ) is True

    def test_buy_exceeds_limit(self, cb):
        """Buy with slippage over 0.1% should reject."""
        # intended 100, actual 100.2 → 0.2% slippage
        assert cb.check_slippage(
            intended_price=100.0, actual_price=100.2, side="buy",
        ) is False

    def test_buy_exact_limit(self, cb):
        """Slippage exactly at 0.1% should pass."""
        assert cb.check_slippage(
            intended_price=100.0, actual_price=100.1, side="buy",
        ) is True

    def test_sell_within_limit(self, cb):
        """Sell with slippage within limit should pass."""
        # intended 100, actual 99.95 → 0.05% slippage
        assert cb.check_slippage(
            intended_price=100.0, actual_price=99.95, side="sell",
        ) is True

    def test_sell_exceeds_limit(self, cb):
        """Sell with slippage over limit should reject."""
        assert cb.check_slippage(
            intended_price=100.0, actual_price=99.8, side="sell",
        ) is False

    def test_no_slippage(self, cb):
        """No slippage should always pass."""
        assert cb.check_slippage(
            intended_price=100.0, actual_price=100.0, side="buy",
        ) is True

    def test_negative_slippage_favorable(self, cb):
        """Favorable fill (negative slippage) should always pass."""
        assert cb.check_slippage(
            intended_price=100.0, actual_price=99.9, side="buy",
        ) is True


# ── adjust_for_gap_risk ─────────────────────────────────────────────


class TestGapRisk:
    def test_default_multiplier(self, cb):
        """Default gap_multiplier is 1.5 → 5% becomes 7.5%."""
        assert cb.adjust_for_gap_risk(sl_distance_pct=0.05) == pytest.approx(0.075)

    def test_custom_multiplier(self):
        """Custom multiplier applied correctly."""
        cb = CircuitBreaker(gap_multiplier=2.0)
        assert cb.adjust_for_gap_risk(sl_distance_pct=0.05) == pytest.approx(0.10)

    def test_zero_sl_distance(self, cb):
        """Zero SL distance should return zero."""
        assert cb.adjust_for_gap_risk(sl_distance_pct=0.0) == pytest.approx(0.0)

    def test_small_sl_distance(self, cb):
        """Small SL distance still scales correctly."""
        assert cb.adjust_for_gap_risk(sl_distance_pct=0.001) == pytest.approx(0.0015)


# ── check_directional_exposure ───────────────────────────────────────


class TestDirectionalExposure:
    def test_within_limit(self):
        """Net directional exposure within 60% should pass."""
        positions = [
            {"side": "long",  "notional": 500.0},
            {"side": "short", "notional": 300.0},
        ]
        # net long = 500 - 300 = 200, equity=1000 → 20%
        assert check_directional_exposure(
            positions=positions, equity=1000.0,
        ) is True

    def test_exceeds_limit(self):
        """Net directional exposure above 60% should fail."""
        positions = [
            {"side": "long",  "notional": 800.0},
            {"side": "short", "notional": 100.0},
        ]
        # net long = 700, equity=1000 → 70%
        assert check_directional_exposure(
            positions=positions, equity=1000.0,
        ) is False

    def test_exactly_at_limit(self):
        """Exactly 60% exposure should pass."""
        positions = [
            {"side": "long",  "notional": 600.0},
        ]
        assert check_directional_exposure(
            positions=positions, equity=1000.0,
        ) is True

    def test_no_positions(self):
        """No positions should always pass."""
        assert check_directional_exposure(
            positions=[], equity=1000.0,
        ) is True

    def test_balanced_positions(self):
        """Equal long/short should pass (0% net exposure)."""
        positions = [
            {"side": "long",  "notional": 500.0},
            {"side": "short", "notional": 500.0},
        ]
        assert check_directional_exposure(
            positions=positions, equity=1000.0,
        ) is True

    def test_short_heavy_exceeds(self):
        """Net short exposure above limit should fail."""
        positions = [
            {"side": "long",  "notional": 100.0},
            {"side": "short", "notional": 800.0},
        ]
        # net short = 700, equity=1000 → 70%
        assert check_directional_exposure(
            positions=positions, equity=1000.0,
        ) is False


# ── should_pause_trading ────────────────────────────────────────────


class TestConsecutiveLoss:
    def test_no_losses(self):
        """0 losses → ok."""
        assert should_pause_trading(consecutive_losses=0) == "ok"

    def test_two_losses(self):
        """2 losses → ok."""
        assert should_pause_trading(consecutive_losses=2) == "ok"

    def test_three_losses(self):
        """3 losses → pause."""
        assert should_pause_trading(consecutive_losses=3) == "pause"

    def test_four_losses(self):
        """4 losses → pause."""
        assert should_pause_trading(consecutive_losses=4) == "pause"

    def test_five_losses(self):
        """5 losses → halt."""
        assert should_pause_trading(consecutive_losses=5) == "halt"

    def test_six_losses(self):
        """6 losses → halt."""
        assert should_pause_trading(consecutive_losses=6) == "halt"

    def test_custom_thresholds(self):
        """Custom thresholds should work."""
        assert should_pause_trading(
            consecutive_losses=1, pause_at=1, halt_at=2,
        ) == "pause"
        assert should_pause_trading(
            consecutive_losses=2, pause_at=1, halt_at=2,
        ) == "halt"


# ── CircuitBreaker.should_halt ──────────────────────────────────────


class TestShouldHalt:
    def test_not_halted_initially(self, cb):
        """New instance should not be halted."""
        assert cb.should_halt() is False

    def test_halt_returns_true_during_halt(self, cb):
        """After triggering halt, should_halt returns True."""
        cb.trigger_halt()
        assert cb.should_halt() is True

    def test_halt_expires(self, cb):
        """After halt duration passes, should_halt returns False."""
        cb.trigger_halt()
        # simulate time passing
        cb._halt_until = time.time() - 1
        assert cb.should_halt() is False
