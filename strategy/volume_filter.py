"""Volume spike detection filter."""

from loguru import logger


def calculate_volume_avg(volumes: list[float], period: int) -> list[float]:
    """Calculate rolling average of volumes.

    Args:
        volumes: List of volume values.
        period: Rolling window size.

    Returns:
        List of rolling averages.
    """
    if len(volumes) < period:
        return []

    averages: list[float] = []
    for i in range(period, len(volumes) + 1):
        window = volumes[i - period : i]
        averages.append(sum(window) / period)

    return averages


class VolumeFilter:
    """Volume spike detection.

    Confirms entries during active market by detecting
    volume spikes above rolling average.
    """

    def __init__(
        self,
        avg_period: int = 20,
        spike_multiplier: float = 1.5,
    ):
        self.avg_period = avg_period
        self.spike_multiplier = spike_multiplier

    def evaluate(self, candles: list) -> dict:
        """Evaluate candles for volume spike.

        Args:
            candles: List of [ts, o, h, l, c, v] candles.

        Returns:
            Dict with 'current_volume', 'avg_volume', 'is_spike'.
        """
        if not candles:
            return {"current_volume": 0, "avg_volume": 0, "is_spike": False}

        volumes = [c[5] for c in candles]
        current_volume = volumes[-1]

        if len(volumes) < self.avg_period:
            logger.debug(
                f"Volume filter: not enough data ({len(volumes)} < {self.avg_period})"
            )
            return {
                "current_volume": current_volume,
                "avg_volume": 0,
                "is_spike": False,
            }

        # Use the last avg_period volumes for the average (including current)
        window = volumes[-self.avg_period :]
        avg_volume = sum(window) / self.avg_period

        is_spike = current_volume > (avg_volume * self.spike_multiplier)

        logger.debug(
            f"Volume filter: current={current_volume:.0f} "
            f"avg={avg_volume:.0f} spike={is_spike}"
        )

        return {
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "is_spike": is_spike,
        }
