"""RSI filter for overbought/oversold detection."""

from loguru import logger


def calculate_rsi(data: list[float], period: int = 14) -> float | None:
    """Calculate RSI from price data.

    Uses Wilder's smoothing method for subsequent averages:
        avg_gain = (prev_avg_gain * (period - 1) + current_gain) / period
        avg_loss = (prev_avg_loss * (period - 1) + current_loss) / period

    Args:
        data: List of closing prices (need at least period + 1).
        period: RSI period (default 14).

    Returns:
        RSI value (0-100) or None if insufficient data.
    """
    if len(data) < period + 1:
        return None

    # Step 1: price changes
    changes = [data[i] - data[i - 1] for i in range(1, len(data))]

    # Step 2: separate gains and losses
    gains = [c if c > 0 else 0.0 for c in changes]
    losses = [-c if c < 0 else 0.0 for c in changes]

    # Step 3: first averages are SMA over the first 'period' values
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Step 4: Wilder's smoothing for remaining values
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    # Step 5: compute RSI
    if avg_loss == 0 and avg_gain == 0:
        return 50.0  # no price movement
    if avg_loss == 0:
        return 100.0  # all gains, no losses

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(rsi, 4)


class RsiFilter:
    """RSI-based entry filter.

    Signal zones (default thresholds):
        RSI > 80         -> block   (extreme overbought)
        70 <= RSI <= 80  -> allow_short only
        30 < RSI < 70    -> allow_long + allow_short
        20 <= RSI <= 30  -> allow_long only
        RSI < 20         -> block   (extreme oversold)
    """

    def __init__(
        self,
        period: int = 14,
        overbought: int = 70,
        oversold: int = 30,
    ):
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def evaluate(self, candles: list) -> dict:
        """Evaluate candles for RSI filter.

        Args:
            candles: List of [ts, o, h, l, c, v] OHLCV candles.

        Returns:
            Dict with 'rsi' and 'action' keys.
            action is one of: "allow_long", "allow_short", "allow_both", "block".
        """
        closes = [candle[4] for candle in candles]
        rsi = calculate_rsi(closes, self.period)

        if rsi is None:
            logger.debug(f"RSI: insufficient data ({len(closes)} candles)")
            return {"rsi": None, "action": "block"}

        # Extreme zones -> block everything
        extreme_high = self.overbought + 10  # > 80 by default
        extreme_low = self.oversold - 10     # < 20 by default

        if rsi > extreme_high:
            logger.info(f"RSI={rsi:.1f} > {extreme_high} - extreme overbought, block")
            return {"rsi": rsi, "action": "block"}

        if rsi < extreme_low:
            logger.info(f"RSI={rsi:.1f} < {extreme_low} - extreme oversold, block")
            return {"rsi": rsi, "action": "block"}

        # Overbought zone (70-80): only short
        if rsi >= self.overbought:
            logger.info(f"RSI={rsi:.1f} in overbought zone - allow_short only")
            return {"rsi": rsi, "action": "allow_short"}

        # Oversold zone (20-30): only long
        if rsi <= self.oversold:
            logger.info(f"RSI={rsi:.1f} in oversold zone - allow_long only")
            return {"rsi": rsi, "action": "allow_long"}

        # Neutral zone: allow both directions
        logger.debug(f"RSI={rsi:.1f} neutral - allow both directions")
        return {"rsi": rsi, "action": "allow_both"}
