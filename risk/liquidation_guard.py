"""Liquidation guard: distance-to-liquidation monitoring.

Checks how close an open position is to its liquidation price and
recommends actions (warn / close) when the distance drops below
configurable thresholds.
"""

from loguru import logger


class LiquidationGuard:
    """Monitor distance-to-liquidation for open positions.

    Args:
        close_threshold_pct: Fraction of price between current and
            liquidation below which the position should be closed
            (default 0.20 = 20 %).
        warn_threshold_pct: Fraction below which a warning is emitted
            (default 0.30 = 30 %).  Must be > ``close_threshold_pct``.
    """

    def __init__(
        self,
        close_threshold_pct: float = 0.20,
        warn_threshold_pct: float = 0.30,
    ) -> None:
        if warn_threshold_pct <= close_threshold_pct:
            raise ValueError(
                "warn_threshold_pct must be greater than "
                "close_threshold_pct"
            )
        self.close_threshold_pct = close_threshold_pct
        self.warn_threshold_pct = warn_threshold_pct

    def check(
        self,
        side: str,
        entry_price: float,
        current_price: float,
        liquidation_price: float,
    ) -> dict:
        """Evaluate liquidation risk for a single position.

        Args:
            side: ``"long"`` or ``"short"``.
            entry_price: Average entry price.
            current_price: Current mark / last price.
            liquidation_price: Exchange-reported liquidation price.

        Returns:
            Dict with keys ``at_risk`` (bool), ``distance_pct``
            (float), ``action`` (``"none"`` / ``"warn"`` / ``"close"``).
        """
        if side not in ("long", "short"):
            raise ValueError(
                f"side must be 'long' or 'short', got '{side}'"
            )

        # Edge: zero entry price → cannot compute
        if entry_price <= 0:
            return {
                "at_risk": False,
                "distance_pct": 0.0,
                "action": "none",
                "reason": "invalid entry price",
            }

        # Edge: zero liquidation price → no liquidation risk
        if liquidation_price <= 0:
            return {
                "at_risk": False,
                "distance_pct": float("inf"),
                "action": "none",
                "reason": "no liquidation price set",
            }

        # Calculate distance as fraction of current price
        if side == "long":
            distance = current_price - liquidation_price
        else:
            distance = liquidation_price - current_price

        # Guard against negative current_price
        if current_price <= 0:
            return {
                "at_risk": True,
                "distance_pct": 0.0,
                "action": "close",
                "reason": "invalid current price",
            }

        distance_pct = distance / abs(current_price)

        # Already past liquidation
        if distance_pct <= 0:
            return {
                "at_risk": True,
                "distance_pct": distance_pct,
                "action": "close",
                "reason": "at or past liquidation price",
            }

        # Determine action
        if distance_pct <= self.close_threshold_pct:
            action = "close"
            reason = (
                f"distance {distance_pct:.1%} <= "
                f"close threshold {self.close_threshold_pct:.0%}"
            )
        elif distance_pct <= self.warn_threshold_pct:
            action = "warn"
            reason = (
                f"distance {distance_pct:.1%} <= "
                f"warn threshold {self.warn_threshold_pct:.0%}"
            )
        else:
            action = "none"
            reason = "safe distance from liquidation"

        at_risk = action != "none"

        if at_risk:
            logger.warning(
                f"Liquidation risk: {side} position "
                f"distance={distance_pct:.1%} action={action}"
            )

        return {
            "at_risk": at_risk,
            "distance_pct": distance_pct,
            "action": action,
            "reason": reason,
        }
