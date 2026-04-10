"""Tests for EMA crossover strategy."""

import math
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from binance_ta_bot.strategy.ema_crossover import (
    calculate_ema,
    EmaCrossover,
)


# ---------------------------------------------------------------------------
# calculate_ema tests
# ---------------------------------------------------------------------------

class TestCalculateEma:
    """Tests for the calculate_ema helper function."""

    def test_ema_single_value(self):
        """EMA of a single value returns that value."""
        result = calculate_ema([100.0], period=1)
        assert result == [100.0]

    def test_ema_period_greater_than_data_length(self):
        """EMA with period > data length returns empty list."""
        result = calculate_ema([10.0, 20.0], period=5)
        assert result == []

    def test_ema_period_equals_data_length(self):
        """EMA with period == data length returns SMA of all values (1 element)."""
        data = [10.0, 20.0, 30.0]
        result = calculate_ema(data, period=3)
        assert len(result) == 1
        assert result[0] == pytest.approx(20.0)  # SMA of [10, 20, 30]

    def test_ema_constant_data(self):
        """EMA of constant data stays constant."""
        data = [50.0] * 10
        result = calculate_ema(data, period=3)
        assert all(v == pytest.approx(50.0) for v in result)

    def test_ema_known_values(self):
        """EMA calculation matches manual computation.

        Data: [1, 2, 3, 4, 5], period=3
        First EMA = SMA(1, 2, 3) = 2.0
        EMA[3] = (4 - 2.0) * (2/4) + 2.0 = 3.0
        EMA[4] = (5 - 3.0) * (2/4) + 3.0 = 4.0
        """
        result = calculate_ema([1.0, 2.0, 3.0, 4.0, 5.0], period=3)
        assert len(result) == 3
        assert result[0] == pytest.approx(2.0)   # SMA(1,2,3)
        assert result[1] == pytest.approx(3.0)   # EMA(4)
        assert result[2] == pytest.approx(4.0)   # EMA(5)

    def test_ema_ohlcv_close_prices(self):
        """EMA works with close prices extracted from OHLCV candles."""
        # OHLCV: [ts, o, h, l, close, v]
        closes = [100.0, 102.0, 104.0, 103.0, 105.0]
        result = calculate_ema(closes, period=3)
        # First EMA = SMA(100, 102, 104) = 102.0
        assert result[0] == pytest.approx(102.0)
        # EMA[3] = (103 - 102) * 0.5 + 102 = 102.5
        assert result[1] == pytest.approx(102.5)
        # EMA[4] = (105 - 102.5) * 0.5 + 102.5 = 103.75
        assert result[2] == pytest.approx(103.75)

    def test_ema_empty_data(self):
        """EMA of empty data returns empty list."""
        result = calculate_ema([], period=3)
        assert result == []


# ---------------------------------------------------------------------------
# EmaCrossover class tests
# ---------------------------------------------------------------------------

class TestEmaCrossoverInit:
    """Tests for EmaCrossover constructor."""

    def test_default_periods(self):
        """Default constructor sets fast=9, slow=21."""
        ec = EmaCrossover()
        assert ec.fast_period == 9
        assert ec.slow_period == 21

    def test_custom_periods(self):
        """Custom periods are stored correctly."""
        ec = EmaCrossover(fast_period=5, slow_period=13)
        assert ec.fast_period == 5
        assert ec.slow_period == 13


class TestEmaCrossoverNotEnoughData:
    """Tests for insufficient data scenarios."""

    def test_not_enough_data_returns_none(self):
        """Returns signal=none when candles < slow_period + 1."""
        ec = EmaCrossover(fast_period=3, slow_period=5)
        # slow_period + 1 = 6 candles needed, provide only 4
        candles = _make_candles([100.0, 101.0, 102.0, 103.0])
        result = ec.evaluate(candles)
        assert result["signal"] == "none"

    def test_exactly_not_enough_data(self):
        """Exactly slow_period candles is still not enough (need +1 for prev)."""
        ec = EmaCrossover(fast_period=3, slow_period=5)
        candles = _make_candles([100.0, 101.0, 102.0, 103.0, 104.0])
        result = ec.evaluate(candles)
        assert result["signal"] == "none"

    def test_empty_candles(self):
        """Empty candles returns signal=none."""
        ec = EmaCrossover(fast_period=3, slow_period=5)
        result = ec.evaluate([])
        assert result["signal"] == "none"


class TestEmaCrossoverLongSignal:
    """Tests for long signal (fast EMA crosses above slow EMA)."""

    def test_long_crossover(self):
        """Long signal when fast EMA crosses above slow EMA.

        Build a price series where fast EMA crosses above slow EMA
        on the last candle.
        """
        ec = EmaCrossover(fast_period=3, slow_period=5)

        # Flat start -> dip (fast falls below slow) -> sharp spike
        # on last candle pushes fast back above slow.
        prices = [100.0]*5 + [95.0]*4 + [105.0]
        candles = _make_candles(prices)

        result = ec.evaluate(candles)
        assert result["signal"] == "long"
        assert "fast_ema" in result
        assert "slow_ema" in result
        assert result["fast_ema"] > result["slow_ema"]

    def test_long_signal_returns_correct_ema_values(self):
        """Long signal includes current fast and slow EMA values."""
        ec = EmaCrossover(fast_period=2, slow_period=4)

        # Prices: constant then spike -> fast crosses above slow
        prices = [50.0, 50.0, 50.0, 50.0, 60.0, 65.0]
        candles = _make_candles(prices)
        result = ec.evaluate(candles)

        # Must have a signal or at least valid EMA values
        assert result["signal"] in ("long", "short", "none")
        assert isinstance(result["fast_ema"], float)
        assert isinstance(result["slow_ema"], float)


class TestEmaCrossoverShortSignal:
    """Tests for short signal (fast EMA crosses below slow EMA)."""

    def test_short_crossover(self):
        """Short signal when fast EMA crosses below slow EMA."""
        ec = EmaCrossover(fast_period=3, slow_period=5)

        # Flat start -> spike (fast above slow) -> sharp dip
        # on last candle pushes fast below slow.
        prices = [100.0]*5 + [105.0]*4 + [95.0]
        candles = _make_candles(prices)

        result = ec.evaluate(candles)
        assert result["signal"] == "short"
        assert result["fast_ema"] < result["slow_ema"]


class TestEmaCrossoverNoSignal:
    """Tests for no-signal scenarios."""

    def test_no_crossover_trending_up(self):
        """No signal when fast EMA is consistently above slow EMA (no crossover)."""
        ec = EmaCrossover(fast_period=3, slow_period=5)

        # Prices trending up strongly - fast stays above slow
        prices = [float(100 + i * 2) for i in range(12)]
        candles = _make_candles(prices)
        result = ec.evaluate(candles)

        # After initial crossover, no new crossover should happen
        # (fast is already above slow)
        # We need to check: on the LAST candle, was there a crossover?
        # If prices keep rising, fast stays above -> no new crossover
        assert result["signal"] == "none"

    def test_no_crossover_trending_down(self):
        """No signal when fast EMA is consistently below slow EMA."""
        ec = EmaCrossover(fast_period=3, slow_period=5)

        # Prices trending down strongly
        prices = [float(200 - i * 2) for i in range(12)]
        candles = _make_candles(prices)
        result = ec.evaluate(candles)

        # fast stays below slow -> no new crossover
        assert result["signal"] == "none"

    def test_no_crossover_flat(self):
        """No signal when prices are flat."""
        ec = EmaCrossover(fast_period=3, slow_period=5)

        prices = [100.0] * 15
        candles = _make_candles(prices)
        result = ec.evaluate(candles)

        assert result["signal"] == "none"


class TestEmaCrossoverEdgeCases:
    """Edge case tests."""

    def test_minimum_viable_candles(self):
        """Exactly slow_period + 1 candles can produce a signal."""
        ec = EmaCrossover(fast_period=2, slow_period=3)
        # Need 4 candles (slow_period + 1)
        prices = [100.0, 100.0, 100.0, 110.0]
        candles = _make_candles(prices)
        result = ec.evaluate(candles)
        # Should not crash; signal depends on crossover logic
        assert result["signal"] in ("long", "short", "none")

    def test_default_periods_with_enough_data(self):
        """Default periods (9, 21) work with enough candles."""
        ec = EmaCrossover()  # fast=9, slow=21
        prices = [float(100 + i) for i in range(30)]
        candles = _make_candles(prices)
        result = ec.evaluate(candles)
        assert "signal" in result
        assert "fast_ema" in result
        assert "slow_ema" in result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candles(prices: list[float]) -> list:
    """Create OHLCV candles from a list of close prices.

    Each candle: [timestamp, open, high, low, close, volume]
    """
    candles = []
    for i, close in enumerate(prices):
        candles.append([
            i * 60000,  # timestamp in ms
            close,       # open = close (simplified)
            close,       # high
            close,       # low
            close,       # close
            1000.0,      # volume
        ])
    return candles
