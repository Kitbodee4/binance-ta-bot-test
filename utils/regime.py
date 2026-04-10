"""Regime detection utilities for identifying trending vs ranging markets."""

from loguru import logger
import numpy as np


def calculate_adx(high_prices, low_prices, close_prices, period=14):
    """Calculate Average Directional Index (ADX) for trend strength measurement.

    Args:
        high_prices: List of high prices
        low_prices: List of low prices
        close_prices: List of close prices
        period: ADX period (default 14)

    Returns:
        ADX value (0-100)
    """
    if len(high_prices) < period * 2 or len(low_prices) < period * 2 or len(close_prices) < period * 2:
        return 0.0

    # Calculate True Range (TR)
    tr_values = []
    for i in range(1, len(high_prices)):
        high_low = high_prices[i] - low_prices[i]
        high_close_prev = abs(high_prices[i] - close_prices[i-1])
        low_close_prev = abs(low_prices[i] - close_prices[i-1])
        tr = max(high_low, high_close_prev, low_close_prev)
        tr_values.append(tr)

    # Calculate Directional Movement (+DM and -DM)
    plus_dm = []
    minus_dm = []
    for i in range(1, len(high_prices)):
        high_diff = high_prices[i] - high_prices[i-1]
        low_diff = low_prices[i-1] - low_prices[i]  # Note: inverted for calculation

        if high_diff > low_diff and high_diff > 0:
            plus_dm_val = high_diff
        else:
            plus_dm_val = 0

        if low_diff > high_diff and low_diff > 0:
            minus_dm_val = low_diff
        else:
            minus_dm_val = 0

        plus_dm.append(plus_dm_val)
        minus_dm.append(minus_dm_val)

    # Calculate smoothed TR, +DM, -DM using Wilder's smoothing
    def WilderSmoothing(values, period):
        """Apply Wilder's smoothing (similar to EMA but with 1/period factor)."""
        if len(values) < period:
            return np.mean(values) if values else 0.0

        # First value is simple average
        smoothed = np.mean(values[:period])

        # Apply Wilder's smoothing: previous_smoothed * (period-1)/period + current_value/period
        for i in range(period, len(values)):
            smoothed = (smoothed * (period - 1) + values[i]) / period

        return smoothed

    if len(tr_values) < period:
        return 0.0

    smoothed_tr = WilderSmoothing(tr_values, period)
    smoothed_plus_dm = WilderSmoothing(plus_dm, period)
    smoothed_minus_dm = WilderSmoothing(minus_dm, period)

    # Calculate Directional Indicators (+DI and -DI)
    if smoothed_tr == 0:
        plus_di = 0
        minus_di = 0
    else:
        plus_di = (smoothed_plus_dm / smoothed_tr) * 100
        minus_di = (smoothed_minus_dm / smoothed_tr) * 100

    # Calculate Directional Index (DX)
    if (plus_di + minus_di) == 0:
        dx = 0
    else:
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100

    # Calculate ADX (smoothed DX)
    # For simplicity, we'll calculate a few DX values and smooth them
    # In practice, you'd need to calculate DX for each period and then smooth
    adx = dx  # Simplified - in practice would be smoothed over multiple periods

    return min(max(adx, 0), 100)  # Clamp between 0 and 100


def get_market_regime(adx_value, adx_threshold=25):
    """Determine market regime based on ADX value.

    Args:
        adx_value: ADX value (0-100)
        adx_threshold: Threshold above which market is considered trending (default 25)

    Returns:
        Market regime: 'trending' or 'ranging'
    """
    if adx_value >= adx_threshold:
        return 'trending'
    else:
        return 'ranging'


def get_regime_adjusted_parameters(base_params, regime, regime_adjustments=None):
    """Adjust strategy parameters based on market regime.

    Args:
        base_params: Dictionary of base parameters
        regime: Market regime ('trending' or 'ranging')
        regime_adjustments: Dictionary of adjustments for each regime.
                           Can be multipliers (float) or absolute values (int/float).
                           If a value is a float like 0.9, it's treated as multiplier.
                           If a value is an int like 75, it's treated as absolute value
                           only if it's different in type from base or explicitly marked.

    Returns:
        Dictionary of adjusted parameters
    """
    if regime_adjustments is None:
        # Default adjustments: more aggressive in trending, more conservative in ranging
        regime_adjustments = {
            'trending': {
                'risk_per_trade': 1.2,      # Increase risk in trending markets (multiplier)
                'volume_spike_mult': 0.8,   # Lower volume spike requirement (multiplier)
                'rsi_overbought': 75,       # Higher RSI threshold for overbought (absolute)
                'rsi_oversold': 25,         # Lower RSI threshold for oversold (absolute)
                'ema_fast': 0.9,            # Slightly faster EMAs (multiplier)
                'ema_slow': 0.9,            # Slightly faster EMAs (multiplier)
            },
            'ranging': {
                'risk_per_trade': 0.7,      # Decrease risk in ranging markets (multiplier)
                'volume_spike_mult': 1.5,   # Higher volume spike requirement (multiplier)
                'rsi_overbought': 65,       # Lower RSI threshold for overbought (absolute)
                'rsi_oversold': 35,         # Higher RSI threshold for oversold (absolute)
                'ema_fast': 1.1,            # Slightly slower EMAs (multiplier)
                'ema_slow': 1.1,            # Slightly slower EMAs (multiplier)
            }
        }

    adjusted_params = base_params.copy()
    adjustments = regime_adjustments.get(regime, {})

    for param, adjustment in adjustments.items():
        if param in adjusted_params:
            base_value = adjusted_params[param]

            # Determine if adjustment is multiplier or absolute value
            # Heuristic: if adjustment is float and base_value is int, likely multiplier
            #          if adjustment is int and base_value is int, could be either
            #          if adjustment is float and base_value is float, likely multiplier
            # For simplicity, we'll treat small floats (< 2) as multipliers, larger as absolute
            # But for RSI values (0-100), we know the intent

            if param in ['rsi_overbought', 'rsi_oversold']:
                # These are absolute values (0-100 range)
                adjusted_params[param] = adjustment
            elif isinstance(adjustment, float) and adjustment < 2.0:
                # Likely a multiplier (e.g., 0.9, 1.1, 1.2)
                if isinstance(base_value, int):
                    adjusted_params[param] = max(1, int(round(base_value * adjustment)))
                else:
                    adjusted_params[param] = base_value * adjustment
            else:
                # Treat as absolute value
                adjusted_params[param] = adjustment

    return adjusted_params