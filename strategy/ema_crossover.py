"""EMA crossover strategy for signal generation."""

from loguru import logger


def calculate_ema(data: list[float], period: int) -> list[float]:
    """Calculate Exponential Moving Average.

    Args:
        data: List of price values (e.g., closing prices).
        period: EMA period.

    Returns:
        List of EMA values (length = len(data) - period + 1).
    """
    if not data or period < 1 or len(data) < period:
        return []

    # First EMA value = SMA of first `period` values
    sma = sum(data[:period]) / period
    ema_values = [sma]

    multiplier = 2.0 / (period + 1)

    for price in data[period:]:
        ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)

    return ema_values


class EmaCrossover:
    """EMA crossover signal generator.

    Generates LONG when fast EMA crosses above slow EMA.
    Generates SHORT when fast EMA crosses below slow EMA.
    """

    def __init__(self, fast_period: int = 9, slow_period: int = 21):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def evaluate(self, candles: list) -> dict:
        """Evaluate OHLCV candles for crossover signal.

        Args:
            candles: List of [ts, o, h, l, c, v] candles.

        Returns:
            Dict with 'signal', 'fast_ema', 'slow_ema' keys.
        """
        default = {"signal": "none", "fast_ema": 0.0, "slow_ema": 0.0}

        if not candles or len(candles) < self.slow_period + 1:
            return default

        # Extract close prices (index 4 in OHLCV)
        closes = [candle[4] for candle in candles]

        fast_ema = calculate_ema(closes, self.fast_period)
        slow_ema = calculate_ema(closes, self.slow_period)

        if not fast_ema or not slow_ema:
            return default

        # Align lengths: both start at index (slow_period - 1) in closes
        # fast_ema starts at index (fast_period - 1), slow_ema at (slow_period - 1)
        # The slow EMA starts later, so we offset fast_ema to match
        offset = self.slow_period - self.fast_period
        if offset > 0:
            fast_ema = fast_ema[offset:]

        if len(fast_ema) < 2 or len(slow_ema) < 2:
            return default

        # Current and previous EMA values
        curr_fast = fast_ema[-1]
        curr_slow = slow_ema[-1]
        prev_fast = fast_ema[-2]
        prev_slow = slow_ema[-2]

        # Detect crossover on current candle
        # Long: fast crosses above slow (prev_fast <= prev_slow AND curr_fast > curr_slow)
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            logger.info(
                f"EMA crossover LONG: fast={curr_fast:.4f} > slow={curr_slow:.4f}"
            )
            return {"signal": "long", "fast_ema": curr_fast, "slow_ema": curr_slow}

        # Short: fast crosses below slow (prev_fast >= prev_slow AND curr_fast < curr_slow)
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            logger.info(
                f"EMA crossover SHORT: fast={curr_fast:.4f} < slow={curr_slow:.4f}"
            )
            return {"signal": "short", "fast_ema": curr_fast, "slow_ema": curr_slow}

        return {"signal": "none", "fast_ema": curr_fast, "slow_ema": curr_slow}
