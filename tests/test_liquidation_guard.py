"""Tests for LiquidationGuard - distance-to-liquidation check."""

import pytest


@pytest.fixture
def guard_cls():
    """Import LiquidationGuard inside fixture (project convention)."""
    from newtrade.binance_ta_bot.risk.liquidation_guard import LiquidationGuard
    return LiquidationGuard


class TestLiquidationGuardInit:
    """Tests for LiquidationGuard initialization."""

    def test_default_thresholds(self, guard_cls):
        guard = guard_cls()
        assert guard.close_threshold_pct == 0.20
        assert guard.warn_threshold_pct == 0.30

    def test_custom_thresholds(self, guard_cls):
        guard = guard_cls(
            close_threshold_pct=0.15,
            warn_threshold_pct=0.25,
        )
        assert guard.close_threshold_pct == 0.15
        assert guard.warn_threshold_pct == 0.25

    def test_warn_must_be_greater_than_close(self, guard_cls):
        with pytest.raises(ValueError, match="warn_threshold_pct"):
            guard_cls(
                close_threshold_pct=0.30,
                warn_threshold_pct=0.20,
            )


class TestLiquidationGuardLongPosition:
    """Tests for long position liquidation checks."""

    @pytest.fixture
    def guard(self, guard_cls):
        return guard_cls(
            close_threshold_pct=0.20,
            warn_threshold_pct=0.30,
        )

    def test_safe_position(self, guard):
        """Position far from liquidation - no risk."""
        result = guard.check(
            side="long",
            entry_price=67500.0,
            current_price=67600.0,
            liquidation_price=33750.0,
        )
        assert result["at_risk"] is False
        assert result["action"] == "none"
        assert result["distance_pct"] > 0.30

    def test_warn_zone(self, guard):
        """Position in warning zone (25% from liquidation)."""
        # Liq at 50000, current at 66667 -> distance = (66667-50000)/66667 = 25%
        result = guard.check(
            side="long",
            entry_price=67500.0,
            current_price=66667.0,
            liquidation_price=50000.0,
        )
        assert result["at_risk"] is True
        assert result["action"] == "warn"
        assert 0.20 < result["distance_pct"] < 0.30

    def test_close_zone(self, guard):
        """Position in close zone (15% from liquidation)."""
        # Liq at 56667, current at 66667 -> distance = (66667-56667)/66667 = 15%
        result = guard.check(
            side="long",
            entry_price=67500.0,
            current_price=66667.0,
            liquidation_price=56667.0,
        )
        assert result["at_risk"] is True
        assert result["action"] == "close"
        assert result["distance_pct"] < 0.20

    def test_at_liquidation(self, guard):
        """Current price equals liquidation price."""
        result = guard.check(
            side="long",
            entry_price=67500.0,
            current_price=50000.0,
            liquidation_price=50000.0,
        )
        assert result["at_risk"] is True
        assert result["action"] == "close"
        assert result["distance_pct"] == 0.0


class TestLiquidationGuardShortPosition:
    """Tests for short position liquidation checks."""

    @pytest.fixture
    def guard(self, guard_cls):
        return guard_cls(
            close_threshold_pct=0.20,
            warn_threshold_pct=0.30,
        )

    def test_safe_short(self, guard):
        """Short position far from liquidation."""
        result = guard.check(
            side="short",
            entry_price=67500.0,
            current_price=67400.0,
            liquidation_price=100000.0,
        )
        assert result["at_risk"] is False
        assert result["action"] == "none"

    def test_warn_zone_short(self, guard):
        """Short in warning zone (25% from liquidation)."""
        # Liq at 83334, current at 66667
        # distance = (83334-66667)/66667 = 25%
        result = guard.check(
            side="short",
            entry_price=67500.0,
            current_price=66667.0,
            liquidation_price=83334.0,
        )
        assert result["at_risk"] is True
        assert result["action"] == "warn"

    def test_close_zone_short(self, guard):
        """Short in close zone (~18% from liquidation)."""
        # Liq at 78431, current at 66667
        # distance = (78431-66667)/66667 = 17.6% < 20% close threshold
        result = guard.check(
            side="short",
            entry_price=67500.0,
            current_price=66667.0,
            liquidation_price=78431.0,
        )
        assert result["at_risk"] is True
        assert result["action"] == "close"


class TestLiquidationGuardEdgeCases:
    """Tests for edge cases."""

    @pytest.fixture
    def guard(self, guard_cls):
        return guard_cls()

    def test_invalid_side(self, guard):
        with pytest.raises(ValueError, match="side"):
            guard.check(
                side="invalid",
                entry_price=67500.0,
                current_price=67500.0,
                liquidation_price=33750.0,
            )

    def test_zero_entry_price(self, guard):
        result = guard.check(
            side="long",
            entry_price=0.0,
            current_price=67500.0,
            liquidation_price=33750.0,
        )
        assert result["action"] == "none"

    def test_zero_liquidation_price(self, guard):
        """Zero liquidation price means no liquidation risk."""
        result = guard.check(
            side="long",
            entry_price=67500.0,
            current_price=67500.0,
            liquidation_price=0.0,
        )
        assert result["at_risk"] is False
        assert result["action"] == "none"
        assert result["distance_pct"] == float("inf")

    def test_negative_current_price(self, guard):
        result = guard.check(
            side="long",
            entry_price=67500.0,
            current_price=-100.0,
            liquidation_price=33750.0,
        )
        assert result["action"] == "close"

    def test_current_below_liquidation_long(self, guard):
        """Current price already below liquidation (long)."""
        result = guard.check(
            side="long",
            entry_price=67500.0,
            current_price=30000.0,
            liquidation_price=33750.0,
        )
        assert result["at_risk"] is True
        assert result["action"] == "close"
        assert result["distance_pct"] <= 0.0
