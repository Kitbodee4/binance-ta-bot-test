"""TDD tests for RiskManager - written BEFORE implementation."""

import pytest
from unittest.mock import patch


@pytest.fixture
def risk_mgr():
    """Default RiskManager instance."""
    from newtrade.binance_ta_bot.risk.risk_manager import RiskManager
    return RiskManager()


@pytest.fixture
def custom_risk_mgr():
    """RiskManager with custom params."""
    from newtrade.binance_ta_bot.risk.risk_manager import RiskManager
    return RiskManager(
        risk_per_trade=0.02,
        max_leverage=5,
        max_positions=5,
        daily_loss_limit=0.05,
        weekly_loss_limit=0.10,
    )


# ─────────────────────────────────────────────
# Position Sizing
# ─────────────────────────────────────────────

class TestCalculatePositionSize:
    """Test position sizing logic."""

    def test_basic_position_size(self, risk_mgr):
        """Given known inputs, should return expected contract size."""
        equity = 10000.0
        entry_price = 67500.0
        stop_loss = 67000.0
        # risk_amount = 10000 * 0.01 = 100
        # sl_distance = (67500 - 67000) / 67500 = 0.0074074
        # size_usd = 100 / 0.0074074 = 13500
        # contracts = 13500 / 67500 = 0.2
        size = risk_mgr.calculate_position_size(equity, entry_price, stop_loss)
        assert size == pytest.approx(0.2, rel=1e-4)

    def test_size_respects_max_leverage(self, risk_mgr):
        """Position notional must not exceed equity * max_leverage."""
        equity = 10000.0
        entry_price = 100.0
        stop_loss = 99.9   # tiny SL → would produce huge size
        size = risk_mgr.calculate_position_size(equity, entry_price, stop_loss)
        notional = size * entry_price
        max_notional = equity * 3  # max_leverage=3
        assert notional <= max_notional

    def test_short_position_size(self, risk_mgr):
        """Short: SL above entry, size still positive."""
        equity = 10000.0
        entry_price = 67500.0
        stop_loss = 68000.0
        size = risk_mgr.calculate_position_size(equity, entry_price, stop_loss)
        assert size > 0

    def test_zero_equity_returns_zero(self, risk_mgr):
        """Zero equity → zero size."""
        size = risk_mgr.calculate_position_size(0.0, 67500.0, 67000.0)
        assert size == 0.0

    def test_sl_equals_entry_returns_zero(self, risk_mgr):
        """SL at entry → zero size (no risk distance)."""
        size = risk_mgr.calculate_position_size(10000.0, 67500.0, 67500.0)
        assert size == 0.0

    def test_negative_equity_returns_zero(self, risk_mgr):
        """Negative equity → zero size."""
        size = risk_mgr.calculate_position_size(-1000.0, 67500.0, 67000.0)
        assert size == 0.0

    def test_custom_risk_pct(self, custom_risk_mgr):
        """Custom risk_per_trade=0.02 should double the size."""
        equity = 10000.0
        entry_price = 67500.0
        stop_loss = 67000.0
        # risk_amount = 10000 * 0.02 = 200
        # sl_distance = (67500 - 67000) / 67500 = 0.0074074
        # size_usd = 200 / 0.0074074 = 27000
        # contracts = 27000 / 67500 = 0.4
        size = custom_risk_mgr.calculate_position_size(equity, entry_price, stop_loss)
        assert size == pytest.approx(0.4, rel=1e-4)


# ─────────────────────────────────────────────
# Position Limit
# ─────────────────────────────────────────────

class TestPositionLimit:
    """Test max concurrent positions check."""

    def test_under_limit_approved(self, risk_mgr):
        """2 open positions with max=3 → approved."""
        positions = [
            {"symbol": "BTC/USDT:USDT", "side": "long"},
            {"symbol": "ETH/USDT:USDT", "side": "short"},
        ]
        assert risk_mgr.check_position_limit(positions) is True

    def test_at_limit_rejected(self, risk_mgr):
        """3 open positions with max=3 → rejected."""
        positions = [
            {"symbol": "BTC/USDT:USDT"},
            {"symbol": "ETH/USDT:USDT"},
            {"symbol": "SOL/USDT:USDT"},
        ]
        assert risk_mgr.check_position_limit(positions) is False

    def test_over_limit_rejected(self, risk_mgr):
        """4 open positions with max=3 → rejected."""
        positions = [{"symbol": f"COIN{i}/USDT"} for i in range(4)]
        assert risk_mgr.check_position_limit(positions) is False

    def test_empty_approved(self, risk_mgr):
        """No positions → approved."""
        assert risk_mgr.check_position_limit([]) is True


# ─────────────────────────────────────────────
# Daily Loss Limit
# ─────────────────────────────────────────────

class TestDailyLossLimit:
    """Test daily loss limit check."""

    def test_within_limit_approved(self, risk_mgr):
        """Daily loss under 3% → approved."""
        assert risk_mgr.check_daily_loss_limit(-200.0, 10000.0) is True

    def test_at_limit_rejected(self, risk_mgr):
        """Daily loss exactly 3% → rejected."""
        assert risk_mgr.check_daily_loss_limit(-300.0, 10000.0) is False

    def test_over_limit_rejected(self, risk_mgr):
        """Daily loss over 3% → rejected."""
        assert risk_mgr.check_daily_loss_limit(-350.0, 10000.0) is False

    def test_positive_pnl_approved(self, risk_mgr):
        """Positive PnL always approved."""
        assert risk_mgr.check_daily_loss_limit(500.0, 10000.0) is True


# ─────────────────────────────────────────────
# Weekly Loss Limit
# ─────────────────────────────────────────────

class TestWeeklyLossLimit:
    """Test weekly loss limit check."""

    def test_within_limit_approved(self, risk_mgr):
        """Weekly loss under 8% → approved."""
        assert risk_mgr.check_weekly_loss_limit(-700.0, 10000.0) is True

    def test_at_limit_rejected(self, risk_mgr):
        """Weekly loss exactly 8% → rejected."""
        assert risk_mgr.check_weekly_loss_limit(-800.0, 10000.0) is False

    def test_over_limit_rejected(self, risk_mgr):
        """Weekly loss over 8% → rejected."""
        assert risk_mgr.check_weekly_loss_limit(-850.0, 10000.0) is False


# ─────────────────────────────────────────────
# Directional Exposure
# ─────────────────────────────────────────────

class TestDirectionalExposure:
    """Test max net directional exposure check."""

    def test_balanced_exposure_approved(self, risk_mgr):
        """Balanced long/short → approved."""
        positions = [
            {"side": "long", "notional": 3000.0},
            {"side": "short", "notional": 3000.0},
        ]
        assert risk_mgr.check_directional_exposure(positions, 10000.0) is True

    def test_excessive_long_rejected(self, risk_mgr):
        """Long exposure > 60% equity → rejected."""
        positions = [
            {"side": "long", "notional": 4000.0},
            {"side": "long", "notional": 3000.0},
        ]
        assert risk_mgr.check_directional_exposure(positions, 10000.0) is False

    def test_excessive_short_rejected(self, risk_mgr):
        """Short exposure > 60% equity → rejected."""
        positions = [
            {"side": "short", "notional": 3500.0},
            {"side": "short", "notional": 3500.0},
        ]
        assert risk_mgr.check_directional_exposure(positions, 10000.0) is False

    def test_empty_positions_approved(self, risk_mgr):
        """No positions → approved."""
        assert risk_mgr.check_directional_exposure([], 10000.0) is True

    def test_net_exposure_counts(self, risk_mgr):
        """Net = long_notional - short_notional, compare |net| to max."""
        positions = [
            {"side": "long", "notional": 8000.0},
            {"side": "short", "notional": 3000.0},
            # net long = 5000, which is 50% of 10000 → under 60%
        ]
        assert risk_mgr.check_directional_exposure(positions, 10000.0) is True

    def test_net_exposure_over_limit(self, risk_mgr):
        """Net directional > 60% → rejected."""
        positions = [
            {"side": "long", "notional": 8000.0},
            {"side": "short", "notional": 1000.0},
            # net long = 7000, which is 70% of 10000 → over 60%
        ]
        assert risk_mgr.check_directional_exposure(positions, 10000.0) is False


# ─────────────────────────────────────────────
# SL/TP Calculation
# ─────────────────────────────────────────────

class TestSlTpCalculation:
    """Test stop-loss and take-profit calculation."""

    def test_long_sl_below_entry(self, risk_mgr):
        """Long: SL should be below entry."""
        result = risk_mgr.calculate_sl_tp(
            entry_price=67500.0,
            side="long",
            swing_low=67000.0,
            swing_high=68000.0,
        )
        assert result["stop_loss"] < 67500.0

    def test_long_tp_above_entry(self, risk_mgr):
        """Long: TP should be above entry."""
        result = risk_mgr.calculate_sl_tp(
            entry_price=67500.0,
            side="long",
            swing_low=67000.0,
            swing_high=68000.0,
        )
        assert result["take_profit"] > 67500.0

    def test_short_sl_above_entry(self, risk_mgr):
        """Short: SL should be above entry."""
        result = risk_mgr.calculate_sl_tp(
            entry_price=67500.0,
            side="short",
            swing_low=67000.0,
            swing_high=68000.0,
        )
        assert result["stop_loss"] > 67500.0

    def test_short_tp_below_entry(self, risk_mgr):
        """Short: TP should be below entry."""
        result = risk_mgr.calculate_sl_tp(
            entry_price=67500.0,
            side="short",
            swing_low=67000.0,
            swing_high=68000.0,
        )
        assert result["take_profit"] < 67500.0

    def test_long_risk_reward_ratio(self, risk_mgr):
        """Long: TP distance should be 2x SL distance (1:2 R:R)."""
        entry = 67500.0
        result = risk_mgr.calculate_sl_tp(
            entry_price=entry,
            side="long",
            swing_low=67000.0,
            swing_high=68000.0,
        )
        risk = entry - result["stop_loss"]
        reward = result["take_profit"] - entry
        assert reward == pytest.approx(2 * risk, rel=1e-4)

    def test_short_risk_reward_ratio(self, risk_mgr):
        """Short: TP distance should be 2x SL distance (1:2 R:R)."""
        entry = 67500.0
        result = risk_mgr.calculate_sl_tp(
            entry_price=entry,
            side="short",
            swing_low=67000.0,
            swing_high=68000.0,
        )
        risk = result["stop_loss"] - entry
        reward = entry - result["take_profit"]
        assert reward == pytest.approx(2 * risk, rel=1e-4)

    def test_min_sl_distance_enforced(self, risk_mgr):
        """SL distance must be >= 0.5% of entry."""
        entry = 67500.0
        result = risk_mgr.calculate_sl_tp(
            entry_price=entry,
            side="long",
            swing_low=67470.0,   # only 0.044% below → too tight
            swing_high=68000.0,
        )
        sl_distance_pct = (entry - result["stop_loss"]) / entry
        assert sl_distance_pct >= 0.005

    def test_max_sl_distance_enforced(self, risk_mgr):
        """SL distance must be <= 3% of entry."""
        entry = 67500.0
        result = risk_mgr.calculate_sl_tp(
            entry_price=entry,
            side="long",
            swing_low=60000.0,   # way below → would be >3%
            swing_high=68000.0,
        )
        sl_distance_pct = (entry - result["stop_loss"]) / entry
        assert sl_distance_pct <= 0.03

    def test_invalid_side_raises(self, risk_mgr):
        """Invalid side should raise ValueError."""
        with pytest.raises(ValueError, match="side"):
            risk_mgr.calculate_sl_tp(
                entry_price=67500.0,
                side="invalid",
                swing_low=67000.0,
                swing_high=68000.0,
            )


# ─────────────────────────────────────────────
# Consecutive Loss Tracking
# ─────────────────────────────────────────────

class TestConsecutiveLoss:
    """Test consecutive loss protection."""

    def test_zero_losses_trade(self, risk_mgr):
        """0 consecutive losses → trade normally."""
        result = risk_mgr.check_consecutive_loss(0)
        assert result["action"] == "trade"

    def test_one_loss_trade(self, risk_mgr):
        """1 consecutive loss → trade normally."""
        result = risk_mgr.check_consecutive_loss(1)
        assert result["action"] == "trade"

    def test_two_losses_trade(self, risk_mgr):
        """2 consecutive losses → trade normally."""
        result = risk_mgr.check_consecutive_loss(2)
        assert result["action"] == "trade"

    def test_three_losses_pause(self, risk_mgr):
        """3 consecutive losses → pause."""
        result = risk_mgr.check_consecutive_loss(3)
        assert result["action"] == "pause"

    def test_four_losses_pause(self, risk_mgr):
        """4 consecutive losses → still pause."""
        result = risk_mgr.check_consecutive_loss(4)
        assert result["action"] == "pause"

    def test_five_losses_halt(self, risk_mgr):
        """5 consecutive losses → halt."""
        result = risk_mgr.check_consecutive_loss(5)
        assert result["action"] == "halt"

    def test_six_losses_halt(self, risk_mgr):
        """6 consecutive losses → halt."""
        result = risk_mgr.check_consecutive_loss(6)
        assert result["action"] == "halt"

    def test_pause_has_duration(self, risk_mgr):
        """Pause action should include duration_hours."""
        result = risk_mgr.check_consecutive_loss(3)
        assert "duration_hours" in result
        assert result["duration_hours"] == 4

    def test_halt_has_reason(self, risk_mgr):
        """Halt action should include reason."""
        result = risk_mgr.check_consecutive_loss(5)
        assert "reason" in result
        assert "halt" in result["reason"].lower()


# ─────────────────────────────────────────────
# Check All Limits (Integration)
# ─────────────────────────────────────────────

class TestCheckAllLimits:
    """Test the unified check_all_limits method."""

    def test_all_ok_approved(self, risk_mgr):
        """All limits OK → approved."""
        result = risk_mgr.check_all_limits(
            equity=10000.0,
            daily_pnl=-100.0,
            weekly_pnl=-200.0,
            open_positions=[
                {"symbol": "BTC/USDT:USDT", "side": "long", "notional": 3000.0},
            ],
            consecutive_losses=1,
        )
        assert result["approved"] is True

    def test_position_limit_rejected(self, risk_mgr):
        """Max positions exceeded → rejected with reason."""
        positions = [{"symbol": f"COIN{i}/USDT"} for i in range(3)]
        result = risk_mgr.check_all_limits(
            equity=10000.0,
            daily_pnl=0.0,
            weekly_pnl=0.0,
            open_positions=positions,
            consecutive_losses=0,
        )
        assert result["approved"] is False
        assert "position" in result["reason"].lower()

    def test_daily_loss_rejected(self, risk_mgr):
        """Daily loss limit hit → rejected with reason."""
        result = risk_mgr.check_all_limits(
            equity=10000.0,
            daily_pnl=-350.0,
            weekly_pnl=-350.0,
            open_positions=[],
            consecutive_losses=0,
        )
        assert result["approved"] is False
        assert "daily" in result["reason"].lower()

    def test_weekly_loss_rejected(self, risk_mgr):
        """Weekly loss limit hit → rejected with reason."""
        result = risk_mgr.check_all_limits(
            equity=10000.0,
            daily_pnl=-100.0,
            weekly_pnl=-900.0,
            open_positions=[],
            consecutive_losses=0,
        )
        assert result["approved"] is False
        assert "weekly" in result["reason"].lower()

    def test_consecutive_loss_halt_rejected(self, risk_mgr):
        """Consecutive loss halt → rejected with reason."""
        result = risk_mgr.check_all_limits(
            equity=10000.0,
            daily_pnl=0.0,
            weekly_pnl=0.0,
            open_positions=[],
            consecutive_losses=5,
        )
        assert result["approved"] is False
        assert "halt" in result["reason"].lower()

    def test_directional_exposure_rejected(self, risk_mgr):
        """Excessive directional exposure → rejected with reason."""
        positions = [
            {"side": "long", "notional": 5000.0},
            {"side": "long", "notional": 3000.0},
        ]
        result = risk_mgr.check_all_limits(
            equity=10000.0,
            daily_pnl=0.0,
            weekly_pnl=0.0,
            open_positions=positions,
            consecutive_losses=0,
        )
        assert result["approved"] is False
        assert "exposure" in result["reason"].lower()

    def test_returns_dict_with_required_keys(self, risk_mgr):
        """Result should have 'approved' and 'reason' keys."""
        result = risk_mgr.check_all_limits(
            equity=10000.0,
            daily_pnl=0.0,
            weekly_pnl=0.0,
            open_positions=[],
            consecutive_losses=0,
        )
        assert "approved" in result
        assert "reason" in result
