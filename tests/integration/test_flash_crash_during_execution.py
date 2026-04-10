"""Integration test: Flash crash during position management.

Scenario:
1. BotEngine opens a position (MANAGING state)
2. Price drops 5% in <60s (flash crash)
3. Circuit breaker detects crash
4. ALL positions are emergency closed
"""

import pytest
from unittest.mock import MagicMock, patch, call


@pytest.fixture
def wired_engine():
    """Fully wired BotEngine with mocked dependencies for flash crash test."""
    from newtrade.binance_ta_bot.core.bot_engine import BotEngine
    from newtrade.binance_ta_bot.risk.circuit_breaker import CircuitBreaker

    exchange_client = MagicMock()
    pair_scanner = MagicMock()
    strategy = MagicMock()
    risk_manager = MagicMock()
    order_executor = MagicMock()
    state_manager = MagicMock()
    circuit_breaker = CircuitBreaker(
        flash_crash_pct=0.05,
        halt_duration_min=60,
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


class TestFlashCrashDuringExecution:
    """Integration: flash crash closes ALL positions."""

    def test_flash_crash_closes_all_positions(self, wired_engine):
        """When flash crash detected on one position, ALL are closed."""
        engine = wired_engine

        # Simulate two open positions
        pos_btc = {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 66500.0,
            "take_profit": 69500.0,
        }
        pos_eth = {
            "symbol": "ETH/USDT:USDT",
            "side": "long",
            "size": 1.0,
            "entry_price": 3500.0,
            "stop_loss": 3400.0,
            "take_profit": 3700.0,
        }
        engine._positions = [pos_btc, pos_eth]
        engine._state = "MANAGING"

        # BTC crashes 6% (flash crash), ETH is normal
        def mock_ticker(symbol):
            if "BTC" in symbol:
                return {"last": 63450.0}  # -6% from 67500
            return {"last": 3510.0}  # ETH normal

        engine.exchange_client.fetch_ticker.side_effect = mock_ticker

        # Run position management
        engine._manage_positions()

        # Circuit breaker should be halted
        assert engine.circuit_breaker.should_halt() is True

        # ALL positions should be closed (close_position called for both)
        assert engine.order_executor.close_position.call_count == 2

        # Verify both symbols were closed
        closed_symbols = [
            c.kwargs.get("symbol") or c.args[0]
            for c in engine.order_executor.close_position.call_args_list
        ]
        assert "BTC/USDT:USDT" in closed_symbols
        assert "ETH/USDT:USDT" in closed_symbols

        # State should be IDLE after emergency close
        assert engine._state == "IDLE"

    def test_sl_hit_triggers_exit(self, wired_engine):
        """Normal SL hit closes only that position."""
        engine = wired_engine

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

        # Price hits SL
        engine.exchange_client.fetch_ticker.return_value = {
            "last": 66900.0
        }

        engine._manage_positions()

        # Only one close, not flash crash halt
        engine.order_executor.close_position.assert_called_once()
        assert engine.circuit_breaker.should_halt() is False
        assert engine._state == "IDLE"

    def test_tp_hit_triggers_exit(self, wired_engine):
        """TP hit closes the position."""
        engine = wired_engine

        pos = {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 66500.0,
            "take_profit": 69500.0,
        }
        engine._positions = [pos]
        engine._state = "MANAGING"

        engine.exchange_client.fetch_ticker.return_value = {
            "last": 69600.0
        }

        engine._manage_positions()

        engine.order_executor.close_position.assert_called_once()
        assert engine._state == "IDLE"

    def test_circuit_breaker_skips_scan(self, wired_engine):
        """When circuit breaker is halted, _tick skips scanning."""
        engine = wired_engine

        # Trigger halt
        engine.circuit_breaker.trigger_halt()
        assert engine.circuit_breaker.should_halt() is True

        # _tick should return immediately without scanning
        engine._tick()

        engine.pair_scanner.scan.assert_not_called()
        assert engine._state == "IDLE"

    def test_short_position_flash_crash(self, wired_engine):
        """Flash crash on short position (price spikes up 6%)."""
        engine = wired_engine

        pos = {
            "symbol": "BTC/USDT:USDT",
            "side": "short",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 70000.0,
            "take_profit": 65000.0,
        }
        engine._positions = [pos]
        engine._state = "MANAGING"

        # Price spikes up 6% against short
        engine.exchange_client.fetch_ticker.return_value = {
            "last": 71550.0
        }

        engine._manage_positions()

        # Flash crash detected, position closed
        assert engine.circuit_breaker.should_halt() is True
        engine.order_executor.close_position.assert_called_once()
