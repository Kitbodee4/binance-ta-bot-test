"""Tests for volatility calculation utilities."""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    # Try relative import first (when run from tests directory)
    from utils.volatility import (
        calculate_atr,
        calculate_atr_percentage,
        get_volatility_regime,
        get_dynamic_timeframes
    )
except ImportError:
    # Fallback to absolute import (when run from project root)
    from binance_ta_bot.utils.volatility import (
        calculate_atr,
        calculate_atr_percentage,
        get_volatility_regime,
        get_dynamic_timeframes
    )


def test_calculate_atr():
    """Test ATR calculation with known values."""
    # Simple test data: constant price movement of 1
    high_prices = [10, 11, 12, 13, 14, 15]
    low_prices = [9, 10, 11, 12, 13, 14]
    close_prices = [9.5, 10.5, 11.5, 12.5, 13.5, 14.5]

    atr = calculate_atr(high_prices, low_prices, close_prices, period=3)
    # Calculate True Range for each period:
    # Period 1: high=11, low=10, close_prev=9.5 => TR = max(1, 1.5, 0.5) = 1.5
    # Period 2: high=12, low=11, close_prev=10.5 => TR = max(1, 1.5, 0.5) = 1.5
    # Period 3: high=13, low=12, close_prev=11.5 => TR = max(1, 1.5, 0.5) = 1.5
    # Period 4: high=14, low=13, close_prev=12.5 => TR = max(1, 1.5, 0.5) = 1.5
    # Period 5: high=15, low=14, close_prev=13.5 => TR = max(1, 1.5, 0.5) = 1.5
    # TR values: [1.5, 1.5, 1.5, 1.5, 1.5]
    # First ATR (period=3): (1.5+1.5+1.5)/3 = 1.5
    # Second ATR: (1.5*2 + 1.5)/3 = 1.5
    # Third ATR: (1.5*2 + 1.5)/3 = 1.5
    assert atr == 1.5


def test_calculate_atr_percentage():
    """Test ATR percentage calculation."""
    high_prices = [100, 101, 102]
    low_prices = [99, 100, 101]
    close_prices = [99.5, 100.5, 101.5]

    atr_pct = calculate_atr_percentage(high_prices, low_prices, close_prices, period=2)
    # Should be a reasonable percentage
    assert 0 <= atr_pct <= 0.1  # Between 0% and 10%


def test_get_volatility_regime():
    """Test volatility regime classification."""
    assert get_volatility_regime(0.01) == 'low'      # < 0.015
    assert get_volatility_regime(0.02) == 'medium'   # 0.015 <= x < 0.035
    assert get_volatility_regime(0.04) == 'high'     # >= 0.035


def test_get_dynamic_timeframes():
    """Test dynamic timeframe adjustment."""
    base_entry = "15m"
    base_trend = "1h"
    base_htf = "4h"

    # Low volatility -> longer timeframes
    entry_tf, trend_tf, htf_tf = get_dynamic_timeframes(base_entry, base_trend, base_htf, 'low')
    assert entry_tf == "1h"
    assert trend_tf == "4h"
    assert htf_tf == "1d"

    # Medium volatility -> base timeframes
    entry_tf, trend_tf, htf_tf = get_dynamic_timeframes(base_entry, base_trend, base_htf, 'medium')
    assert entry_tf == "15m"
    assert trend_tf == "1h"
    assert htf_tf == "4h"

    # High volatility -> shorter timeframes
    entry_tf, trend_tf, htf_tf = get_dynamic_timeframes(base_entry, base_trend, base_htf, 'high')
    assert entry_tf == "5m"
    assert trend_tf == "15m"
    assert htf_tf == "1h"


if __name__ == "__main__":
    test_calculate_atr()
    test_calculate_atr_percentage()
    test_get_volatility_regime()
    test_get_dynamic_timeframes()
    print("All tests passed!")