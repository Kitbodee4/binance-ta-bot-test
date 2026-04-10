"""Tests for multi-timeframe strategy."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # Add project root

# Import using the same structure as the main code
try:
    # Try relative import first (when run from tests directory)
    from strategy.multi_tf_strategy import (
        detect_trend,
        detect_crossover,
        MultiTimeframeStrategy
    )
except ImportError:
    # Fallback to absolute import (when run from project root)
    from binance_ta_bot.strategy.multi_tf_strategy import (
        detect_trend,
        detect_crossover,
        MultiTimeframeStrategy
    )


def _make_candles(
    count,
    base_price=67000.0,
    trend=0.0,
    base_volume=1000.0,
    volume_spike_at=None,
    spike_mult=2.0,
    interval_ms=900000,
):
    """Generate synthetic OHLCV candles."""
    candles = []
    price = base_price
    for i in range(count):
        open_p = price
        close_p = price + trend
        high_p = max(open_p, close_p) + abs(trend) * 0.5
        low_p = min(open_p, close_p) - abs(trend) * 0.5
        vol = base_volume * spike_mult if i == volume_spike_at else base_volume
        candles.append([
            1711603200000 + i * interval_ms,
            open_p, high_p, low_p, close_p, vol,
        ])
        price = close_p
    return candles


def _make_uptrend_1h(count=250, **kw):
    """1h candles in a clear uptrend (EMA50 > EMA200)."""
    return _make_candles(count, base_price=60000.0, trend=50.0, interval_ms=3600000, **kw)


def _make_downtrend_1h(count=250, **kw):
    """1h candles in a clear downtrend (EMA50 < EMA200)."""
    return _make_candles(count, base_price=70000.0, trend=-50.0, interval_ms=3600000, **kw)


def _make_ranging_1h(count=250, **kw):
    """1h candles in a ranging market (flat price)."""
    return _make_candles(count, base_price=67000.0, trend=0.0, interval_ms=3600000, **kw)


def _make_uptrend_15m(count=50, **kw):
    """15m candles in an uptrend."""
    return _make_candles(count, base_price=67000.0, trend=20.0, **kw)


def _make_downtrend_15m(count=50, **kw):
    """15m candles in a downtrend."""
    return _make_candles(count, base_price=68000.0, trend=-20.0, **kw)


def _make_ema_cross_up_15m(count=50, base_volume=1000.0):
    """15m candles where EMA9 crosses above EMA21 on last candle.

    Phase 1 (42 candles): downtrend so fast EMA < slow EMA.
    Phase 2 (8 candles): uptrend reversal so fast EMA crosses above slow.
    """
    candles = []
    price = 67000.0
    for i in range(42):
        c = price - 50.0
        candles.append([1711603200000 + i * 900000, price, price + 20, price - 20, c, base_volume])
        price = c
    for i in range(count - 42):
        c = price + 100.0
        candles.append([1711603200000 + (42 + i) * 900000, price, price + 20, price - 20, c, base_volume])
        price = c
    return candles


def _make_ema_cross_down_15m(count=50, base_volume=1000.0):
    """15m candles where EMA9 crosses below EMA21 on last candle.

    Phase 1 (42 candles): uptrend so fast EMA > slow EMA.
    Phase 2 (8 candles): downtrend reversal so fast EMA crosses below slow.
    """
    candles = []
    price = 67000.0
    for i in range(42):
        c = price + 50.0
        candles.append([1711603200000 + i * 900000, price, price + 20, price - 20, c, base_volume])
        price = c
    for i in range(count - 42):
        c = price - 100.0
        candles.append([1711603200000 + (42 + i) * 900000, price, price + 20, price - 20, c, base_volume])
        price = c
    return candles


def test_detect_trend():
    """Test trend detection."""
    # Test bullish trend
    candles_1h = [
        [0, 0, 0, 0, 100],  # open, high, low, close
        [0, 0, 0, 0, 101],
        [0, 0, 0, 0, 102],
    ]
    # Extend to have enough data for EMA calculation
    for i in range(100):
        candles_1h.append([0, 0, 0, 0, 100 + i * 0.1])

    trend = detect_trend(candles_1h, fast_period=10, slow_period=30)
    assert trend == "bullish"

    # Test bearish trend
    candles_1h = [
        [0, 0, 0, 0, 200],  # open, high, low, close
        [0, 0, 0, 0, 199],
        [0, 0, 0, 0, 198],
    ]
    for i in range(100):
        candles_1h.append([0, 0, 0, 0, 200 - i * 0.1])

    trend = detect_trend(candles_1h, fast_period=10, slow_period=30)
    assert trend == "bearish"


def test_detect_crossover():
    """Test EMA crossover detection."""
    # Test long signal
    candles = []
    for i in range(30):
        price = 100 + i * 0.5  # Uptrend
        candles.append([0, 0, 0, 0, price])  # [timestamp, open, high, low, close, volume]

    signal = detect_crossover(candles, fast=5, slow=10)
    assert signal == "long"

    # Test short signal
    candles = []
    for i in range(30):
        price = 100 - i * 0.5  # Downtrend
        candles.append([0, 0, 0, 0, price])  # [timestamp, open, high, low, close, volume]

    signal = detect_crossover(candles, fast=5, slow=10)
    assert signal == "short"


def test_multi_timeframe_strategy_initialization():
    """Test strategy initialization."""
    strategy = MultiTimeframeStrategy()
    assert strategy.ema_fast == 9
    assert strategy.ema_slow == 21
    assert strategy.entry_tf == "15m"
    assert strategy.trend_tf == "1h"
    assert strategy.htf_tf == "4h"
    assert strategy.htf_ema_fast == 50
    assert strategy.htf_ema_slow == 200
    assert strategy.dynamic_timeframes == False
    assert strategy.regime_detection == False


def test_multi_timeframe_strategy_evaluate_insufficient_data():
    """Test evaluate with insufficient data."""
    strategy = MultiTimeframeStrategy()
    result = strategy.evaluate([], [], [])
    assert result["signal"] == "none"
    assert result["trend"] == "unknown"
    assert result["htf_trend"] == "unknown"


if __name__ == "__main__":
    test_detect_trend()
    test_detect_crossover()
    test_multi_timeframe_strategy_initialization()
    test_multi_timeframe_strategy_evaluate_insufficient_data()
    print("All tests passed!")