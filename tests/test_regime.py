"""Tests for regime detection utilities."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    # Try relative import first (when run from tests directory)
    from utils.regime import (
        calculate_adx,
        get_market_regime,
        get_regime_adjusted_parameters
    )
except ImportError:
    # Fallback to absolute import (when run from project root)
    from binance_ta_bot.utils.regime import (
        calculate_adx,
        get_market_regime,
        get_regime_adjusted_parameters
    )


def test_get_market_regime():
    """Test market regime classification."""
    assert get_market_regime(30, 25) == 'trending'      # >= threshold
    assert get_market_regime(20, 25) == 'ranging'       # < threshold
    assert get_market_regime(25, 25) == 'trending'      # equal to threshold


def test_get_regime_adjusted_parameters():
    """Test parameter adjustment based on regime."""
    base_params = {
        'risk_per_trade': 0.01,
        'volume_spike_mult': 1.5,
        'rsi_overbought': 70,
        'rsi_oversold': 30,
        'ema_fast': 9,
        'ema_slow': 21
    }

    # Test trending regime
    trending_params = get_regime_adjusted_parameters(base_params, 'trending')
    assert trending_params['risk_per_trade'] > base_params['risk_per_trade']
    assert trending_params['volume_spike_mult'] < base_params['volume_spike_mult']
    assert trending_params['rsi_overbought'] > base_params['rsi_overbought']
    assert trending_params['rsi_oversold'] < base_params['rsi_oversold']

    # Test ranging regime
    ranging_params = get_regime_adjusted_parameters(base_params, 'ranging')
    assert ranging_params['risk_per_trade'] < base_params['risk_per_trade']
    assert ranging_params['volume_spike_mult'] > base_params['volume_spike_mult']
    assert ranging_params['rsi_overbought'] < base_params['rsi_overbought']
    assert ranging_params['rsi_oversold'] > base_params['rsi_oversold']


def test_calculate_adx_basic():
    """Basic test for ADX calculation - should not crash."""
    # Simple test data
    high_prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    low_prices = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
    close_prices = [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5]

    adx = calculate_adx(high_prices, low_prices, close_prices, period=5)
    # Should return a value between 0 and 100
    assert 0 <= adx <= 100


if __name__ == "__main__":
    test_get_market_regime()
    test_get_regime_adjusted_parameters()
    test_calculate_adx_basic()
    print("All regime tests passed!")