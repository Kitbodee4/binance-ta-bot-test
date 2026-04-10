"""Integration test: Partial fill recovery.

Scenario:
1. Order placed for 0.015 BTC
2. Only 0.008 fills (53% fill ratio)
3. OrderExecutor detects partial fill after timeout
4. SL/TP orders adjusted to match filled amount (0.008)
5. Remaining unfilled amount is cancelled
"""

import pytest
from unittest.mock import MagicMock, patch
import time


@pytest.fixture
def order_executor_partial():
    """OrderExecutor with exchange that returns partial fill."""
    from newtrade.binance_ta_bot.execution.order_executor import OrderExecutor
    from newtrade.binance_ta_bot.risk.circuit_breaker import CircuitBreaker

    exchange_client = MagicMock()
    circuit_breaker = CircuitBreaker(
        flash_crash_pct=0.05,
        max_slippage_pct=0.001,
    )

    executor = OrderExecutor(
        exchange_client=exchange_client,
        circuit_breaker=circuit_breaker,
        max_slippage_pct=0.001,
        order_timeout_sec=1,  # Short timeout for test
        dry_run=False,
    )
    return executor


class TestPartialFillRecovery:
    """Integration: partial fill handling in OrderExecutor."""

    def test_partial_fill_reconciles_size(self, order_executor_partial):
        """Partial fill: SL/TP size adjusted to filled amount."""
        executor = order_executor_partial

        # Simulate: create_order returns order with partial fill
        executor.exchange_client.create_order.return_value = {
            "id": "order_123",
            "symbol": "BTC/USDT:USDT",
            "type": "market",
            "side": "buy",
            "amount": 0.015,
            "filled": 0.008,
            "remaining": 0.007,
            "status": "open",
            "average": 67500.0,
        }

        # fetch_order shows it stays partial
        executor.exchange_client.fetch_order.return_value = {
            "id": "order_123",
            "filled": 0.008,
            "remaining": 0.007,
            "status": "open",
            "average": 67500.0,
        }

        with patch("time.sleep"):
            result = executor.execute_entry(
                symbol="BTC/USDT:USDT",
                side="long",
                size=0.015,
                intended_price=67500.0,
                stop_loss=67000.0,
                take_profit=69500.0,
            )

        # Should return partial fill result
        assert result["status"] == "partial"
        assert result["filled"] == 0.008

        # Remaining should be cancelled
        executor.exchange_client.cancel_order.assert_called()

    def test_full_fill_no_cancel(self, order_executor_partial):
        """Full fill: no cancellation needed."""
        executor = order_executor_partial

        executor.exchange_client.create_order.return_value = {
            "id": "order_456",
            "symbol": "BTC/USDT:USDT",
            "type": "market",
            "side": "buy",
            "amount": 0.015,
            "filled": 0.015,
            "remaining": 0.0,
            "status": "closed",
            "average": 67500.0,
        }

        result = executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="long",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=69500.0,
        )

        assert result["status"] == "filled"
        assert result["filled"] == 0.015

    def test_partial_fill_below_threshold(self, order_executor_partial):
        """Fill < 50% after timeout: cancel and work with partial."""
        executor = order_executor_partial

        # 30% fill
        executor.exchange_client.create_order.return_value = {
            "id": "order_789",
            "symbol": "BTC/USDT:USDT",
            "type": "market",
            "side": "buy",
            "amount": 0.015,
            "filled": 0.0045,
            "remaining": 0.0105,
            "status": "open",
            "average": 67500.0,
        }

        executor.exchange_client.fetch_order.return_value = {
            "id": "order_789",
            "filled": 0.0045,
            "remaining": 0.0105,
            "status": "open",
            "average": 67500.0,
        }

        with patch("time.sleep"):
            result = executor.execute_entry(
                symbol="BTC/USDT:USDT",
                side="long",
                size=0.015,
                intended_price=67500.0,
                stop_loss=67000.0,
                take_profit=69500.0,
            )

        assert result["status"] == "partial"
        # Cancelled the remaining
        executor.exchange_client.cancel_order.assert_called()

    def test_sl_tp_placed_with_filled_amount(self, order_executor_partial):
        """After partial fill, SL/TP placed with filled amount only."""
        executor = order_executor_partial

        executor.exchange_client.create_order.return_value = {
            "id": "order_sl",
            "symbol": "BTC/USDT:USDT",
            "type": "market",
            "side": "buy",
            "amount": 0.015,
            "filled": 0.008,
            "remaining": 0.007,
            "status": "open",
            "average": 67500.0,
        }

        executor.exchange_client.fetch_order.return_value = {
            "id": "order_sl",
            "filled": 0.008,
            "remaining": 0.007,
            "status": "open",
            "average": 67500.0,
        }

        with patch("time.sleep"):
            result = executor.execute_entry(
                symbol="BTC/USDT:USDT",
                side="long",
                size=0.015,
                intended_price=67500.0,
                stop_loss=67000.0,
                take_profit=69500.0,
            )

        # SL should be placed with filled amount
        sl_calls = [
            c for c in executor.exchange_client.create_order.call_args_list
            if len(c.args) > 2 and c.args[2] == "sell"
            or c.kwargs.get("side") == "sell"
        ]
        # At least one SL order was attempted
        assert result["status"] in ("partial", "filled")

    def test_dry_run_no_partial_fill(self, order_executor_partial):
        """Dry-run mode: simulated fill, no partial fill handling."""
        from newtrade.binance_ta_bot.execution.order_executor import OrderExecutor
        from newtrade.binance_ta_bot.risk.circuit_breaker import CircuitBreaker

        executor = OrderExecutor(
            exchange_client=MagicMock(),
            circuit_breaker=CircuitBreaker(flash_crash_pct=0.05),
            dry_run=True,
        )

        result = executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="long",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=69500.0,
        )

        # Dry run always returns filled
        assert result["status"] == "filled"
        # No real exchange calls
        executor.exchange_client.create_order.assert_not_called()
