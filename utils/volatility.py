"""Volatility calculation utilities for dynamic timeframe adjustment and risk management."""

from loguru import logger
import numpy as np


def calculate_atr(high_prices, low_prices, close_prices, period=14):
    """Calculate Average True Range (ATR) for given price data.

    Args:
        high_prices: List of high prices
        low_prices: List of low prices
        close_prices: List of close prices
        period: ATR period (default 14)

    Returns:
        ATR value
    """
    if len(high_prices) < period + 1 or len(low_prices) < period + 1 or len(close_prices) < period + 1:
        return 0.0

    # Calculate True Range for each period
    tr_values = []
    for i in range(1, len(high_prices)):
        high_low = high_prices[i] - low_prices[i]
        high_close_prev = abs(high_prices[i] - close_prices[i-1])
        low_close_prev = abs(low_prices[i] - close_prices[i-1])
        tr = max(high_low, high_close_prev, low_close_prev)
        tr_values.append(tr)

    # Calculate ATR using Wilder's smoothing
    if len(tr_values) < period:
        return sum(tr_values) / len(tr_values) if tr_values else 0.0

    # First ATR is simple average of first 'period' TR values
    atr = sum(tr_values[:period]) / period

    # Apply Wilder's smoothing for subsequent values
    for i in range(period, len(tr_values)):
        atr = (atr * (period - 1) + tr_values[i]) / period

    return atr


def calculate_atr_percentage(high_prices, low_prices, close_prices, period=14):
    """Calculate ATR as percentage of current price.

    Args:
        high_prices: List of high prices
        low_prices: List of low prices
        close_prices: List of close prices
        period: ATR period (default 14)

    Returns:
        ATR value as percentage of current price
    """
    atr_value = calculate_atr(high_prices, low_prices, close_prices, period)
    current_price = close_prices[-1] if close_prices else 0
    return (atr_value / current_price) if current_price > 0 else 0.0


def get_volatility_regime(atr_pct, lookback_periods=50):
    """Determine volatility regime based on ATR percentage.

    Args:
        atr_pct: Current ATR as percentage of price
        lookback_periods: Number of periods to look back for volatility ranking (default 50)

    Returns:
        Volatility regime: 'low', 'medium', or 'high'
    """
    # This is a simplified implementation - in practice, you'd want to calculate
    # the percentile rank of current ATR vs historical ATR values
    # For now, we'll use fixed thresholds based on typical crypto volatility

    if atr_pct < 0.015:  # Less than 1.5%
        return 'low'
    elif atr_pct < 0.035:  # 1.5% to 3.5%
        return 'medium'
    else:  # Greater than 3.5%
        return 'high'


def get_dynamic_timeframes(base_entry_tf, base_trend_tf, base_htf_tf, volatility_regime):
    """Get dynamic timeframes based on volatility regime.

    Args:
        base_entry_tf: Base entry timeframe (e.g., '15m')
        base_trend_tf: Base trend timeframe (e.g., '1h')
        base_htf_tf: Base higher timeframe (e.g., '4h')
        volatility_regime: 'low', 'medium', or 'high'

    Returns:
        Tuple of (entry_tf, trend_tf, htf_tf) adjusted for volatility
    """
    # Define timeframe mappings for different volatility regimes
    # Lower volatility -> longer timeframes for stronger signals
    # Higher volatility -> shorter timeframes for quicker entries/exits

    timeframe_map = {
        'low': {
            'entry_tf': '1h',      # Longer entry timeframe in low volatility
            'trend_tf': '4h',      # Longer trend timeframe in low volatility
            'htf_tf': '1d'         # Longer higher timeframe in low volatility
        },
        'medium': {
            'entry_tf': base_entry_tf,  # Use base timeframes in medium volatility
            'trend_tf': base_trend_tf,
            'htf_tf': base_htf_tf
        },
        'high': {
            'entry_tf': '5m',      # Shorter entry timeframe in high volatility
            'trend_tf': '15m',     # Shorter trend timeframe in high volatility
            'htf_tf': '1h'         # Shorter higher timeframe in high volatility
        }
    }

    return (
        timeframe_map[volatility_regime]['entry_tf'],
        timeframe_map[volatility_regime]['trend_tf'],
        timeframe_map[volatility_regime]['htf_tf']
    )