"""Integration test: Price gaps through stop loss.

Scenario:
1. Position has SL at 67000
2. Market gaps from 67500 to 66000 (past SL)
3. BotEngine detects SL hit via current_price <= SL check
4. Position closed at market (gap price), not at SL price
5. Circuit breaker gap risk adjustment is applied to sizing
"""

import pytest
from unittest.mock import MagicMock

from newtrade.binance_ta_bot.risk.circuit_breaker import CircuitBreaker


@pytest.fixture
def engine_with_gap():
    """BotEngine with a long position whose SL will be gapped through."""
    from newtrade.binance_ta_bot.core.bot_engine import BotEngine

    exchange_client = MagicMock()
    pair_scanner = MagicMock()
    strategy = MagicMock()
    risk_manager = MagicMock()
    order_executor = MagicMock()
    state_manager = MagicMock()
    circuit_breaker = CircuitBreaker(
        flash_crash_pct=0.05,
        halt_duration_min=60,
        max_slippage_pct=0.001,
        gap_multiplier=1.5,
    )

    config = {
        "scan_interval_sec": 1,
        "dry_run": True,
        "log_level": "INFO",
    }

    engine = BotEngine(
        exchange_client=exchange_client,
        pair_scanner=pair_scanner,
        strategy=strategy,
        risk_manager=risk_manager,
        order_executor=order_executor,
        state_manager=state_manager,
        circuit_breaker=circuit_breaker,
        config=config,
    )
    return engine


class TestGapThroughStopLoss:
    """Integration: price gaps past stop loss."""

    def test_gap_detected_as_sl_hit(self, engine_with_gap):
        """Price gapped past SL → detected as SL hit, closed at market."""
        engine = engine_with_gap

        pos = {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 69500.0,
        }
        engine._positions = [pos]
        engine._state = "MANAGING"

        # Price gapped from 67000 to 66000 (1.5% gap)
        engine.exchange_client.fetch_ticker.return_value = {
            "last": 66000.0
        }

        engine._manage_positions()

        # SL hit detected (current_price 66000 < SL 67000)
        engine.order_executor.close_position.assert_called_once()
        call_kwargs = engine.order_executor.close_position.call_args
        # close_position called with symbol, side, size
        assert call_kwargs.kwargs.get("symbol") == "BTC/USDT:USDT"

        # State should be IDLE
        assert engine._state == "IDLE"

    def test_gap_multiplier_adjusts_sizing(self):
        """Circuit breaker gap_multiplier increases SL distance for sizing."""
        cb = CircuitBreaker(gap_multiplier=1.5)

        # Original SL distance: 2%
        adjusted = cb.adjust_for_gap_risk(0.02)
        # Should be 2% * 1.5 = 3%
        assert adjusted == pytest.approx(0.03)

    def test_gap_on_short_position(self, engine_with_gap):
        """Short position: price gaps UP past SL."""
        engine = engine_with_gap

        pos = {
            "symbol": "ETH/USDT:USDT",
            "side": "short",
            "size": 1.0,
            "entry_price": 3500.0,
            "stop_loss": 3600.0,
            "take_profit": 3300.0,
        }
        engine._positions = [pos]
        engine._state = "MANAGING"

        # Price gapped up to 3700 (past SL of 3600)
        engine.exchange_client.fetch_ticker.return_value = {
            "last": 3700.0
        }

        engine._manage_positions()

        # SL hit detected (current_price 3700 > SL 3600 for short)
        engine.order_executor.close_position.assert_called_once()
        assert engine._state == "IDLE"

    def test_no_gap_within_normal_sl(self, engine_with_gap):
        """Price within SL range → no exit triggered."""
        engine = engine_with_gap

        pos = {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 69500.0,
        }
        engine._positions = [pos]
        engine._state = "MANAGING"

        # Price at 67200 - above SL, below TP
        engine.exchange_client.fetch_ticker.return_value = {
            "last": 67200.0
        }

        engine._manage_positions()

        # No exit triggered
        engine.order_executor.close_position.assert_not_called()
        assert engine._state == "MANAGING"

    def test_sl_distance_bounds_enforced(self):
        """RiskManager enforces min/max SL distance."""
        from newtrade.binance_ta_bot.risk.risk_manager import RiskManager

        rm = RiskManager(min_sl_pct=0.005, max_sl_pct=0.03)

        # Very tight swing → min SL distance applied
        result = rm.calculate_sl_tp(
            entry_price=67500.0,
            side="long",
            swing_low=67400.0,  # Only 0.15% away
            swing_high=68000.0,
        )
        # Min SL distance = 67500 * 0.005 = 337.5
        sl_distance = 67500.0 - result["stop_loss"]
        assert sl_distance >= 67500.0 * 0.005

        # Very wide swing → max SL distance applied
        result2 = rm.calculate_sl_tp(
            entry_price=67500.0,
            side="long",
            swing_low=65000.0,  # 3.7% away
            swing_high=68000.0,
        )
        sl_distance2 = 67500.0 - result2["stop_loss"]
        assert sl_distance2 <= 67500.0 * 0.03
