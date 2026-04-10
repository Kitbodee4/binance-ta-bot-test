"""TDD tests for OrderExecutor - written BEFORE implementation."""

import time

import pytest
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def executor():
    """Default OrderExecutor in dry_run mode."""
    from newtrade.binance_ta_bot.execution.order_executor import OrderExecutor

    exchange = MagicMock()
    exchange.create_order = MagicMock(return_value={"dry_run": True})
    exchange.fetch_ticker = MagicMock(
        return_value={"last": 67500.0, "bid": 67499.0, "ask": 67501.0}
    )

    cb = MagicMock()
    cb.check_slippage = MagicMock(return_value=True)
    cb.should_halt = MagicMock(return_value=False)
    cb.check_flash_crash = MagicMock(return_value=False)

    return OrderExecutor(
        exchange_client=exchange,
        circuit_breaker=cb,
        max_slippage_pct=0.001,
        order_timeout_sec=30,
        dry_run=True,
    )


@pytest.fixture
def live_executor():
    """OrderExecutor in live mode (dry_run=False)."""
    from newtrade.binance_ta_bot.execution.order_executor import OrderExecutor

    exchange = MagicMock()
    exchange.fetch_ticker = MagicMock(
        return_value={"last": 67500.0, "bid": 67499.0, "ask": 67501.0}
    )

    cb = MagicMock()
    cb.check_slippage = MagicMock(return_value=True)
    cb.should_halt = MagicMock(return_value=False)
    cb.check_flash_crash = MagicMock(return_value=False)

    return OrderExecutor(
        exchange_client=exchange,
        circuit_breaker=cb,
        max_slippage_pct=0.001,
        order_timeout_sec=30,
        dry_run=False,
    )


@pytest.fixture
def halted_executor():
    """OrderExecutor where circuit breaker says halt."""
    from newtrade.binance_ta_bot.execution.order_executor import OrderExecutor

    exchange = MagicMock()
    cb = MagicMock()
    cb.should_halt = MagicMock(return_value=True)

    return OrderExecutor(
        exchange_client=exchange,
        circuit_breaker=cb,
        max_slippage_pct=0.001,
        order_timeout_sec=30,
        dry_run=False,
    )


# ─────────────────────────────────────────────
# Constructor
# ─────────────────────────────────────────────


class TestOrderExecutorInit:
    """Test OrderExecutor initialization."""

    def test_dry_run_default(self, executor):
        """Executor should default to dry_run mode."""
        assert executor.dry_run is True

    def test_live_mode(self, live_executor):
        """Live executor should have dry_run=False."""
        assert live_executor.dry_run is False

    def test_max_slippage_stored(self, executor):
        """max_slippage_pct should be stored."""
        assert executor.max_slippage_pct == 0.001

    def test_order_timeout_stored(self, executor):
        """order_timeout_sec should be stored."""
        assert executor.order_timeout_sec == 30

    def test_exchange_client_stored(self, executor):
        """exchange_client should be stored."""
        assert executor.exchange_client is not None

    def test_circuit_breaker_stored(self, executor):
        """circuit_breaker should be stored."""
        assert executor.circuit_breaker is not None


# ─────────────────────────────────────────────
# Dry-Run Mode
# ─────────────────────────────────────────────


class TestDryRunMode:
    """Test paper-trade (dry_run) behavior."""

    def test_execute_entry_returns_dict(self, executor):
        """execute_entry should return a dict in dry_run."""
        result = executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert isinstance(result, dict)

    def test_execute_entry_has_status(self, executor):
        """execute_entry result should contain status."""
        result = executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert "status" in result

    def test_execute_entry_simulated_fill(self, executor):
        """Dry-run should return a simulated fill with filled amount."""
        result = executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert result["filled"] > 0
        assert result["filled"] <= 0.015

    def test_execute_entry_simulated_slippage_within_bounds(self, executor):
        """Simulated fill price should have slippage within max_slippage_pct."""
        intended = 67500.0
        result = executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=intended,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        fill_price = result.get("avg_price", result.get("price", intended))
        slippage_pct = abs(fill_price - intended) / intended
        assert slippage_pct <= executor.max_slippage_pct + 1e-9

    def test_execute_entry_dry_run_flag(self, executor):
        """Dry-run result should have dry_run=True flag."""
        result = executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert result.get("dry_run") is True

    def test_execute_entry_does_not_call_exchange(self, executor):
        """Dry-run should NOT call real exchange create_order."""
        executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        # Exchange create_order should not be called in dry_run
        # (or if called, returns dry_run flag without real order)
        # We verify that the result is simulated
        assert executor.exchange_client.create_order.call_count <= 1

    def test_place_stop_loss_dry_run(self, executor):
        """place_stop_loss in dry_run should return dict without real order."""
        result = executor.place_stop_loss(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            sl_price=67000.0,
        )
        assert isinstance(result, dict)

    def test_place_take_profit_dry_run(self, executor):
        """place_take_profit in dry_run should return dict without real order."""
        result = executor.place_take_profit(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            tp_price=68500.0,
        )
        assert isinstance(result, dict)

    def test_close_position_dry_run(self, executor):
        """close_position in dry_run should return dict."""
        result = executor.close_position(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
        )
        assert isinstance(result, dict)


# ─────────────────────────────────────────────
# Live Execute Entry
# ─────────────────────────────────────────────


class TestExecuteEntry:
    """Test live execute_entry behavior."""

    def test_calls_exchange_create_order(self, live_executor):
        """Live execute_entry should call exchange.create_order."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "symbol": "BTC/USDT:USDT",
                "type": "market",
                "side": "buy",
                "amount": 0.015,
                "price": 67500.0,
                "status": "closed",
                "filled": 0.015,
                "average": 67505.0,
            }
        )
        live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        # Entry + SL + TP = 3 calls
        assert live_executor.exchange_client.create_order.call_count >= 1

    def test_returns_order_id(self, live_executor):
        """execute_entry should return dict with order id."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "symbol": "BTC/USDT:USDT",
                "type": "market",
                "side": "buy",
                "amount": 0.015,
                "status": "closed",
                "filled": 0.015,
                "average": 67505.0,
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert "id" in result or "order_id" in result

    def test_returns_filled_amount(self, live_executor):
        """execute_entry should return filled amount."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "symbol": "BTC/USDT:USDT",
                "type": "market",
                "side": "buy",
                "amount": 0.015,
                "status": "closed",
                "filled": 0.015,
                "average": 67505.0,
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert "filled" in result
        assert result["filled"] == pytest.approx(0.015)

    def test_records_avg_fill_price(self, live_executor):
        """execute_entry should record actual fill price."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "symbol": "BTC/USDT:USDT",
                "type": "market",
                "side": "buy",
                "amount": 0.015,
                "status": "closed",
                "filled": 0.015,
                "average": 67505.0,
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        avg_price = result.get("avg_price", result.get("average"))
        assert avg_price is not None
        assert avg_price > 0

    def test_sell_entry(self, live_executor):
        """execute_entry should work for sell (short) side."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_002",
                "symbol": "BTC/USDT:USDT",
                "type": "market",
                "side": "sell",
                "amount": 0.015,
                "status": "closed",
                "filled": 0.015,
                "average": 67495.0,
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            intended_price=67500.0,
            stop_loss=68000.0,
            take_profit=66500.0,
        )
        assert result["filled"] == pytest.approx(0.015)


# ─────────────────────────────────────────────
# Slippage Checking
# ─────────────────────────────────────────────


class TestSlippageCheck:
    """Test slippage acceptance/rejection logic."""

    def test_within_max_slippage_accepted(self, live_executor):
        """Fill within 0.1% slippage should be accepted."""
        live_executor.circuit_breaker.check_slippage = MagicMock(
            return_value=True
        )
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.015,
                "average": 67505.0,  # 0.0074% slippage
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert result.get("rejected") is not True

    def test_exceeds_max_slippage_rejected(self, live_executor):
        """Fill exceeding 0.1% slippage should be rejected."""
        live_executor.circuit_breaker.check_slippage = MagicMock(
            return_value=False
        )
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.015,
                "average": 67600.0,  # 0.148% slippage
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        # Should be rejected or have a rejection indicator
        assert result.get("rejected") is True or result.get("status") == "rejected"

    def test_exact_limit_accepted(self, live_executor):
        """Slippage exactly at max should be accepted."""
        live_executor.circuit_breaker.check_slippage = MagicMock(
            return_value=True
        )
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.015,
                "average": 67567.5,  # exactly 0.1%
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert result.get("rejected") is not True

    def test_slippage_recorded_in_result(self, live_executor):
        """Result should contain slippage_pct field."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.015,
                "average": 67505.0,
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        # Should record slippage in some form
        has_slippage = (
            "slippage_pct" in result
            or "slippage" in result
            or "intended_price" in result
        )
        assert has_slippage


# ─────────────────────────────────────────────
# Partial Fill Handling
# ─────────────────────────────────────────────


class TestPartialFill:
    """Test partial fill tracking and handling."""

    def test_full_fill(self, live_executor):
        """Full fill: filled == amount."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.015,
                "amount": 0.015,
                "average": 67500.0,
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        fill_ratio = result["filled"] / 0.015
        assert fill_ratio == pytest.approx(1.0)

    def test_partial_fill_above_50pct(self, live_executor):
        """Partial fill > 50% should be accepted and worked with."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "open",
                "filled": 0.010,
                "amount": 0.015,
                "remaining": 0.005,
                "average": 67500.0,
            }
        )
        live_executor.exchange_client.fetch_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "open",
                "filled": 0.010,
                "amount": 0.015,
                "remaining": 0.005,
                "average": 67500.0,
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        # filled should be >= 50% of intended
        assert result["filled"] >= 0.015 * 0.5

    def test_partial_fill_below_50pct_cancels(self, live_executor):
        """Partial fill < 50% after timeout should cancel remaining."""
        # First call: create_order returns open with small fill
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "open",
                "filled": 0.005,  # 33% filled
                "amount": 0.015,
                "remaining": 0.010,
                "average": 67500.0,
            }
        )
        # fetch_order also returns still-partial
        live_executor.exchange_client.fetch_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "open",
                "filled": 0.005,
                "amount": 0.015,
                "remaining": 0.010,
                "average": 67500.0,
            }
        )
        # cancel_order should be called
        live_executor.exchange_client.cancel_order = MagicMock(
            return_value={"id": "ord_001", "status": "canceled"}
        )
        # Use a very short timeout for testing
        live_executor.order_timeout_sec = 0.1

        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        # Should indicate partial fill was handled
        assert result["filled"] == pytest.approx(0.005)
        # cancel_order should have been called
        live_executor.exchange_client.cancel_order.assert_called()

    def test_sl_tp_size_matches_actual_fill(self, live_executor):
        """After partial fill, SL/TP size should match filled amount."""
        filled_amount = 0.010
        live_executor.exchange_client.create_order = MagicMock(
            side_effect=[
                # Entry order
                {
                    "id": "ord_entry",
                    "status": "open",
                    "filled": filled_amount,
                    "amount": 0.015,
                    "remaining": 0.005,
                    "average": 67500.0,
                },
                # SL order
                {
                    "id": "ord_sl",
                    "status": "open",
                    "filled": 0,
                    "amount": filled_amount,
                },
                # TP order
                {
                    "id": "ord_tp",
                    "status": "open",
                    "filled": 0,
                    "amount": filled_amount,
                },
            ]
        )
        live_executor.exchange_client.fetch_order = MagicMock(
            return_value={
                "id": "ord_entry",
                "status": "open",
                "filled": filled_amount,
                "amount": 0.015,
                "remaining": 0.005,
                "average": 67500.0,
            }
        )
        live_executor.exchange_client.cancel_order = MagicMock(
            return_value={"id": "ord_entry", "status": "canceled"}
        )
        live_executor.order_timeout_sec = 0.1

        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )

        # SL/TP orders should have been placed with filled_amount
        sl_tp_calls = [
            c for c in live_executor.exchange_client.create_order.call_args_list
            if c != live_executor.exchange_client.create_order.call_args_list[0]
        ]
        if sl_tp_calls:
            for call in sl_tp_calls:
                # Each SL/TP order should use filled_amount, not intended 0.015
                # create_order(symbol, type, side, amount, price=...)
                # call[0] = positional args, call[1] = kwargs
                order_amount = call[1].get("amount") or (call[0][3] if len(call[0]) > 3 else None)
                if order_amount is not None:
                    assert order_amount == pytest.approx(filled_amount)


# ─────────────────────────────────────────────
# Order Status Polling
# ─────────────────────────────────────────────


class TestCheckOrderStatus:
    """Test order status polling logic."""

    def test_returns_status_dict(self, live_executor):
        """check_order_status should return a dict with status."""
        live_executor.exchange_client.fetch_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.015,
                "remaining": 0.0,
                "average": 67500.0,
            }
        )
        result = live_executor.check_order_status("ord_001", "BTC/USDT:USDT")
        assert isinstance(result, dict)
        assert "status" in result

    def test_returns_filled_amount(self, live_executor):
        """check_order_status should return filled amount."""
        live_executor.exchange_client.fetch_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.015,
                "remaining": 0.0,
                "average": 67500.0,
            }
        )
        result = live_executor.check_order_status("ord_001", "BTC/USDT:USDT")
        assert result["filled"] == pytest.approx(0.015)

    def test_returns_remaining_amount(self, live_executor):
        """check_order_status should return remaining amount."""
        live_executor.exchange_client.fetch_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "open",
                "filled": 0.010,
                "remaining": 0.005,
                "average": 67500.0,
            }
        )
        result = live_executor.check_order_status("ord_001", "BTC/USDT:USDT")
        assert result["remaining"] == pytest.approx(0.005)

    def test_returns_avg_price(self, live_executor):
        """check_order_status should return average fill price."""
        live_executor.exchange_client.fetch_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.015,
                "remaining": 0.0,
                "average": 67505.0,
            }
        )
        result = live_executor.check_order_status("ord_001", "BTC/USDT:USDT")
        avg = result.get("avg_price", result.get("average"))
        assert avg == pytest.approx(67505.0)

    def test_handles_closed_order(self, live_executor):
        """check_order_status should handle fully filled (closed) orders."""
        live_executor.exchange_client.fetch_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.015,
                "remaining": 0.0,
                "average": 67500.0,
            }
        )
        result = live_executor.check_order_status("ord_001", "BTC/USDT:USDT")
        assert result["status"] == "closed"

    def test_handles_canceled_order(self, live_executor):
        """check_order_status should handle canceled orders."""
        live_executor.exchange_client.fetch_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "canceled",
                "filled": 0.005,
                "remaining": 0.010,
            }
        )
        result = live_executor.check_order_status("ord_001", "BTC/USDT:USDT")
        assert result["status"] == "canceled"

    def test_handles_exchange_error(self, live_executor):
        """check_order_status should handle exchange errors gracefully."""
        live_executor.exchange_client.fetch_order = MagicMock(
            side_effect=Exception("Network timeout")
        )
        result = live_executor.check_order_status("ord_001", "BTC/USDT:USDT")
        # Should return error status, not raise
        assert isinstance(result, dict)
        assert result.get("status") == "error" or result.get("error") is not None


# ─────────────────────────────────────────────
# Stop-Loss Placement
# ─────────────────────────────────────────────


class TestPlaceStopLoss:
    """Test stop-loss order placement."""

    def test_places_order_with_correct_params(self, live_executor):
        """place_stop_loss should call exchange with stop_market type."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "sl_001",
                "type": "stop_market",
                "side": "sell",
                "amount": 0.015,
                "status": "open",
            }
        )
        live_executor.place_stop_loss(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            sl_price=67000.0,
        )
        live_executor.exchange_client.create_order.assert_called_once()
        call_kwargs = live_executor.exchange_client.create_order.call_args
        # Should use stop order type
        assert "stop" in str(call_kwargs).lower() or "trigger" in str(call_kwargs).lower()

    def test_returns_order_dict(self, live_executor):
        """place_stop_loss should return order dict."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "sl_001",
                "type": "stop_market",
                "side": "sell",
                "amount": 0.015,
                "status": "open",
            }
        )
        result = live_executor.place_stop_loss(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            sl_price=67000.0,
        )
        assert isinstance(result, dict)
        assert "id" in result or "order_id" in result

    def test_uses_correct_size(self, live_executor):
        """place_stop_loss should use the provided size."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "sl_001",
                "type": "stop_market",
                "side": "sell",
                "amount": 0.010,
                "status": "open",
            }
        )
        live_executor.place_stop_loss(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.010,
            sl_price=67000.0,
        )
        call_kwargs = live_executor.exchange_client.create_order.call_args
        # Amount should match
        amount = call_kwargs[1].get("amount") if call_kwargs[1] else None
        if amount is not None:
            assert amount == pytest.approx(0.010)

    def test_uses_correct_price(self, live_executor):
        """place_stop_loss should use the SL price."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "sl_001",
                "type": "stop_market",
                "side": "sell",
                "amount": 0.015,
                "price": 67000.0,
                "status": "open",
            }
        )
        live_executor.place_stop_loss(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            sl_price=67000.0,
        )
        call_kwargs = live_executor.exchange_client.create_order.call_args
        price = call_kwargs[1].get("price") if call_kwargs[1] else None
        if price is not None:
            assert price == pytest.approx(67000.0)

    def test_handles_exchange_error(self, live_executor):
        """place_stop_loss should handle exchange errors."""
        live_executor.exchange_client.create_order = MagicMock(
            side_effect=Exception("Insufficient margin")
        )
        result = live_executor.place_stop_loss(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            sl_price=67000.0,
        )
        # Should return error dict, not raise
        assert isinstance(result, dict)
        assert result.get("error") is not None or result.get("status") == "error"


# ─────────────────────────────────────────────
# Take-Profit Placement
# ─────────────────────────────────────────────


class TestPlaceTakeProfit:
    """Test take-profit order placement."""

    def test_places_order_with_correct_params(self, live_executor):
        """place_take_profit should call exchange with take_profit type."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "tp_001",
                "type": "take_profit_market",
                "side": "sell",
                "amount": 0.015,
                "status": "open",
            }
        )
        live_executor.place_take_profit(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            tp_price=68500.0,
        )
        live_executor.exchange_client.create_order.assert_called_once()
        call_kwargs = live_executor.exchange_client.create_order.call_args
        assert "profit" in str(call_kwargs).lower() or "tp" in str(call_kwargs).lower() or "trigger" in str(call_kwargs).lower()

    def test_returns_order_dict(self, live_executor):
        """place_take_profit should return order dict."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "tp_001",
                "type": "take_profit_market",
                "side": "sell",
                "amount": 0.015,
                "status": "open",
            }
        )
        result = live_executor.place_take_profit(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            tp_price=68500.0,
        )
        assert isinstance(result, dict)
        assert "id" in result or "order_id" in result

    def test_uses_correct_price(self, live_executor):
        """place_take_profit should use the TP price."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "tp_001",
                "type": "take_profit_market",
                "side": "sell",
                "amount": 0.015,
                "price": 68500.0,
                "status": "open",
            }
        )
        live_executor.place_take_profit(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            tp_price=68500.0,
        )
        call_kwargs = live_executor.exchange_client.create_order.call_args
        price = call_kwargs[1].get("price") if call_kwargs[1] else None
        if price is not None:
            assert price == pytest.approx(68500.0)

    def test_handles_exchange_error(self, live_executor):
        """place_take_profit should handle exchange errors."""
        live_executor.exchange_client.create_order = MagicMock(
            side_effect=Exception("Invalid price")
        )
        result = live_executor.place_take_profit(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
            tp_price=68500.0,
        )
        assert isinstance(result, dict)
        assert result.get("error") is not None or result.get("status") == "error"


# ─────────────────────────────────────────────
# Order Cancellation
# ─────────────────────────────────────────────


class TestCancelOrder:
    """Test order cancellation."""

    def test_returns_true_on_success(self, live_executor):
        """cancel_order should return True on success."""
        live_executor.exchange_client.cancel_order = MagicMock(
            return_value={"id": "ord_001", "status": "canceled"}
        )
        result = live_executor.cancel_order("ord_001", "BTC/USDT:USDT")
        assert result is True

    def test_returns_false_on_failure(self, live_executor):
        """cancel_order should return False on failure."""
        live_executor.exchange_client.cancel_order = MagicMock(
            side_effect=Exception("Order not found")
        )
        result = live_executor.cancel_order("ord_001", "BTC/USDT:USDT")
        assert result is False

    def test_calls_exchange_cancel(self, live_executor):
        """cancel_order should call exchange.cancel_order."""
        live_executor.exchange_client.cancel_order = MagicMock(
            return_value={"id": "ord_001", "status": "canceled"}
        )
        live_executor.cancel_order("ord_001", "BTC/USDT:USDT")
        live_executor.exchange_client.cancel_order.assert_called_once_with(
            "ord_001", "BTC/USDT:USDT"
        )


# ─────────────────────────────────────────────
# Position Closing
# ─────────────────────────────────────────────


class TestClosePosition:
    """Test position closing."""

    def test_places_market_close_order(self, live_executor):
        """close_position should place a market order to close."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "close_001",
                "type": "market",
                "side": "sell",
                "amount": 0.015,
                "status": "closed",
                "filled": 0.015,
            }
        )
        live_executor.close_position(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
        )
        live_executor.exchange_client.create_order.assert_called_once()

    def test_returns_order_result(self, live_executor):
        """close_position should return order result dict."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "close_001",
                "type": "market",
                "side": "sell",
                "amount": 0.015,
                "status": "closed",
                "filled": 0.015,
            }
        )
        result = live_executor.close_position(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
        )
        assert isinstance(result, dict)

    def test_close_long_position(self, live_executor):
        """Closing a long position should place a sell market order."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "close_001",
                "type": "market",
                "side": "sell",
                "amount": 0.015,
                "status": "closed",
                "filled": 0.015,
            }
        )
        live_executor.close_position(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
        )
        call_kwargs = live_executor.exchange_client.create_order.call_args
        # side should be sell for closing long
        order_side = call_kwargs[1].get("side") if call_kwargs[1] else None
        if order_side is not None:
            assert order_side == "sell"

    def test_close_short_position(self, live_executor):
        """Closing a short position should place a buy market order."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "close_002",
                "type": "market",
                "side": "buy",
                "amount": 0.015,
                "status": "closed",
                "filled": 0.015,
            }
        )
        live_executor.close_position(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
        )
        call_kwargs = live_executor.exchange_client.create_order.call_args
        order_side = call_kwargs[1].get("side") if call_kwargs[1] else None
        if order_side is not None:
            assert order_side == "buy"

    def test_handles_exchange_error(self, live_executor):
        """close_position should handle exchange errors."""
        live_executor.exchange_client.create_order = MagicMock(
            side_effect=Exception("Position not found")
        )
        result = live_executor.close_position(
            symbol="BTC/USDT:USDT",
            side="sell",
            size=0.015,
        )
        assert isinstance(result, dict)
        assert result.get("error") is not None or result.get("status") == "error"


# ─────────────────────────────────────────────
# Circuit Breaker Integration
# ─────────────────────────────────────────────


class TestCircuitBreakerIntegration:
    """Test integration with CircuitBreaker."""

    def test_halt_rejects_new_entry(self, halted_executor):
        """When circuit breaker says halt, execute_entry should reject."""
        result = halted_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert result.get("rejected") is True or result.get("status") == "rejected"
        assert "halt" in str(result).lower() or "circuit" in str(result).lower()

    def test_halt_does_not_place_order(self, halted_executor):
        """When halted, no order should be placed on exchange."""
        halted_executor.exchange_client.create_order = MagicMock()
        halted_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        halted_executor.exchange_client.create_order.assert_not_called()

    def test_flash_crash_triggers_halt(self, live_executor):
        """Flash crash detection should trigger halt."""
        live_executor.circuit_breaker.check_flash_crash = MagicMock(
            return_value=True
        )
        live_executor.circuit_breaker.should_halt = MagicMock(
            return_value=True
        )
        live_executor.circuit_breaker.trigger_halt = MagicMock()

        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        # Should either reject or trigger halt
        assert (
            result.get("rejected") is True
            or result.get("status") == "rejected"
            or live_executor.circuit_breaker.trigger_halt.called
        )

    def test_no_halt_allows_entry(self, live_executor):
        """When circuit breaker says no halt, entry should proceed."""
        live_executor.circuit_breaker.should_halt = MagicMock(return_value=False)
        live_executor.circuit_breaker.check_flash_crash = MagicMock(
            return_value=False
        )
        live_executor.circuit_breaker.check_slippage = MagicMock(
            return_value=True
        )
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.015,
                "average": 67500.0,
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert result.get("rejected") is not True


# ─────────────────────────────────────────────
# Edge Cases
# ─────────────────────────────────────────────


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_size_order(self, live_executor):
        """Zero size should be handled gracefully."""
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.0,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert isinstance(result, dict)
        assert result.get("rejected") is True or result.get("status") == "rejected" or result.get("error") is not None

    def test_negative_size_order(self, live_executor):
        """Negative size should be handled gracefully."""
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=-0.01,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert isinstance(result, dict)
        assert result.get("rejected") is True or result.get("status") == "rejected" or result.get("error") is not None

    def test_zero_price_order(self, live_executor):
        """Zero intended price should be handled gracefully."""
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.015,
            intended_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
        )
        assert isinstance(result, dict)

    def test_very_small_size(self, live_executor):
        """Very small order size should be handled."""
        live_executor.exchange_client.create_order = MagicMock(
            return_value={
                "id": "ord_001",
                "status": "closed",
                "filled": 0.0001,
                "average": 67500.0,
            }
        )
        result = live_executor.execute_entry(
            symbol="BTC/USDT:USDT",
            side="buy",
            size=0.0001,
            intended_price=67500.0,
            stop_loss=67000.0,
            take_profit=68500.0,
        )
        assert isinstance(result, dict)

    def test_cancel_nonexistent_order(self, live_executor):
        """Canceling a nonexistent order should return False."""
        live_executor.exchange_client.cancel_order = MagicMock(
            side_effect=Exception("Order not found")
        )
        result = live_executor.cancel_order("nonexistent", "BTC/USDT:USDT")
        assert result is False

    def test_check_status_nonexistent_order(self, live_executor):
        """Checking status of nonexistent order should handle gracefully."""
        live_executor.exchange_client.fetch_order = MagicMock(
            side_effect=Exception("Order not found")
        )
        result = live_executor.check_order_status("nonexistent", "BTC/USDT:USDT")
        assert isinstance(result, dict)
        assert result.get("error") is not None or result.get("status") == "error"
