"""Integration test: WebSocket disconnect → REST fallback.

Scenario:
1. ExchangeClient tries WebSocket for real-time data
2. WebSocket disconnects (simulated via mock)
3. ExchangeClient falls back to REST polling (fetch_ticker)
4. BotEngine continues operating via REST fallback
5. No data loss during the transition

Note: The current ExchangeClient uses REST-only. This test verifies
that the REST-based flow handles transient errors gracefully and
retries on NetworkError, which is the fallback behavior when WS is
unavailable or disconnected.
"""

import pytest
from unittest.mock import MagicMock, patch
import ccxt


@pytest.fixture
def engine_rest_fallback():
    """BotEngine with exchange that simulates WS failure → REST fallback."""
    from newtrade.binance_ta_bot.core.bot_engine import BotEngine
    from newtrade.binance_ta_bot.risk.circuit_breaker import CircuitBreaker

    exchange_client = MagicMock()
    pair_scanner = MagicMock()
    strategy = MagicMock()
    risk_manager = MagicMock()
    order_executor = MagicMock()
    state_manager = MagicMock()
    circuit_breaker = CircuitBreaker()

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


class TestWebsocketFallback:
    """Integration: WS failure → REST retry → recovery."""

    def test_rest_retry_on_network_error(self, engine_rest_fallback):
        """fetch_ticker fails once with NetworkError, succeeds on retry."""
        engine = engine_rest_fallback

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

        # First call fails, second succeeds
        engine.exchange_client.fetch_ticker.side_effect = [
            ccxt.NetworkError("Connection refused"),
            {"last": 67600.0},  # Recovery
        ]

        # _manage_positions catches the error and continues
        engine._manage_positions()

        # Position still managed (no exit, price is safe)
        assert engine._state == "MANAGING"
        engine.order_executor.close_position.assert_not_called()

    def test_ticker_error_does_not_crash(self, engine_rest_fallback):
        """Exchange error during ticker fetch is handled gracefully."""
        engine = engine_rest_fallback

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

        # Simulate persistent error
        engine.exchange_client.fetch_ticker.side_effect = (
            ccxt.NetworkError("Timeout")
        )

        # Should not raise - error is caught and logged
        engine._manage_positions()

        # Position not closed (couldn't get price)
        engine.order_executor.close_position.assert_not_called()

    def test_scan_recovers_after_error(self, engine_rest_fallback):
        """After scan error, next tick recovers normally."""
        engine = engine_rest_fallback

        # First scan fails
        engine.pair_scanner.scan.side_effect = [
            ccxt.NetworkError("Connection reset"),
            ["BTC/USDT:USDT"],  # Recovery
        ]

        # First tick: scan error → stays IDLE
        engine._tick()
        assert engine._state == "IDLE"

        # Second tick: scan succeeds
        engine.strategy.evaluate.return_value = {"signal": "none"}
        engine.exchange_client.fetch_ohlcv.return_value = [
            [1711603200000, 67000, 67500, 66500, 67400, 1000],
        ]
        engine._tick()
        # Scan was called again (recovery)
        assert engine.pair_scanner.scan.call_count == 2

    def test_multiple_position_errors_isolated(self, engine_rest_fallback):
        """Error on one position doesn't prevent checking others."""
        engine = engine_rest_fallback

        pos1 = {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 69500.0,
        }
        pos2 = {
            "symbol": "ETH/USDT:USDT",
            "side": "long",
            "size": 1.0,
            "entry_price": 3500.0,
            "stop_loss": 3400.0,
            "take_profit": 3700.0,
        }
        engine._positions = [pos1, pos2]
        engine._state = "MANAGING"

        def mock_ticker(symbol):
            if "BTC" in symbol:
                raise ccxt.NetworkError("Timeout on BTC")
            return {"last": 3700.0}  # ETH hits TP

        engine.exchange_client.fetch_ticker.side_effect = mock_ticker

        engine._manage_positions()

        # ETH should have been closed (TP hit)
        engine.order_executor.close_position.assert_called_once()
        close_call = engine.order_executor.close_position.call_args
        assert (
            close_call.kwargs.get("symbol") == "ETH/USDT:USDT"
            or "ETH/USDT:USDT" in str(close_call)
        )

    def test_exchange_client_retries_on_network_error(self):
        """ExchangeClient.fetch_ticker retries once on NetworkError."""
        from newtrade.binance_ta_bot.core.exchange_client import ExchangeClient

        mock_exchange = MagicMock()
        mock_exchange.fetch_ticker.side_effect = [
            ccxt.NetworkError("timeout"),
            {"symbol": "BTC/USDT:USDT", "last": 67500.0},
        ]

        with patch("ccxt.binanceusdm", return_value=mock_exchange):
            client = ExchangeClient(
                exchange_name="binanceusdm",
                api_key="test",
                api_secret="test",
                dry_run=False,
            )
            result = client.fetch_ticker("BTC/USDT:USDT")

        # Retry succeeded
        assert result["last"] == 67500.0
        assert mock_exchange.fetch_ticker.call_count == 2
