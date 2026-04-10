"""TDD tests for ExchangeClient - written BEFORE implementation."""

import pytest
from unittest.mock import MagicMock, patch
import ccxt


class TestExchangeClientInit:
    """Test exchange client initialization."""

    def test_creates_binanceusdm_exchange(self):
        """Should create CCXT binanceusdm instance."""
        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        assert client.exchange_name == "binanceusdm"
        assert client.exchange is not None

    def test_enables_rate_limiting(self):
        """Should enable CCXT rate limiting."""
        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        assert client.exchange.enableRateLimit is True

    def test_dry_run_mode(self):
        """Should support dry-run mode."""
        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
            dry_run=True,
        )
        assert client.dry_run is True


class TestFetchTicker:
    """Test fetch_ticker functionality."""

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_returns_ticker_data(self, mock_ccxt, mock_ticker):
        """Should return ticker data from exchange."""
        mock_exchange = MagicMock()
        mock_exchange.fetch_ticker.return_value = mock_ticker
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        result = client.fetch_ticker("BTC/USDT:USDT")

        assert result["last"] == 67500.0
        assert result["bid"] == 67499.0
        mock_exchange.fetch_ticker.assert_called_once_with(
            "BTC/USDT:USDT"
        )

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_retries_on_network_error(self, mock_ccxt):
        """Should retry on NetworkError."""
        mock_exchange = MagicMock()
        mock_exchange.fetch_ticker.side_effect = [
            ccxt.NetworkError("timeout"),
            {"last": 67500.0},
        ]
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        result = client.fetch_ticker("BTC/USDT:USDT")

        assert result["last"] == 67500.0
        assert mock_exchange.fetch_ticker.call_count == 2


class TestFetchOHLCV:
    """Test fetch_ohlcv functionality."""

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_returns_candles(self, mock_ccxt, mock_ohlcv_15m):
        """Should return OHLCV candles."""
        mock_exchange = MagicMock()
        mock_exchange.fetch_ohlcv.return_value = mock_ohlcv_15m
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        result = client.fetch_ohlcv("BTC/USDT:USDT", "15m", 20)

        assert len(result) == 20
        assert len(result[0]) == 6  # [ts, o, h, l, c, v]

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_supports_multiple_timeframes(self, mock_ccxt):
        """Should accept different timeframes."""
        mock_exchange = MagicMock()
        mock_exchange.fetch_ohlcv.return_value = [
            [1711603200000, 67000, 67500, 66500, 67400, 1000],
        ]
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )

        for tf in ["15m", "1h", "4h"]:
            result = client.fetch_ohlcv("BTC/USDT:USDT", tf)
            assert len(result) >= 1


class TestCreateOrder:
    """Test create_order functionality."""

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_places_market_buy(self, mock_ccxt):
        """Should place market buy order."""
        mock_exchange = MagicMock()
        mock_exchange.create_order.return_value = {
            "id": "order123",
            "symbol": "BTC/USDT:USDT",
            "type": "market",
            "side": "buy",
            "amount": 0.015,
            "status": "closed",
            "filled": 0.015,
        }
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        result = client.create_order(
            symbol="BTC/USDT:USDT",
            order_type="market",
            side="buy",
            amount=0.015,
        )

        assert result["id"] == "order123"
        assert result["status"] == "closed"

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_dry_run_does_not_place_order(self, mock_ccxt):
        """Should simulate order in dry-run mode."""
        mock_exchange = MagicMock()
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
            dry_run=True,
        )
        result = client.create_order(
            symbol="BTC/USDT:USDT",
            order_type="market",
            side="buy",
            amount=0.015,
        )

        assert result["dry_run"] is True
        mock_exchange.create_order.assert_not_called()

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_places_limit_order_with_price(self, mock_ccxt):
        """Should place limit order with price."""
        mock_exchange = MagicMock()
        mock_exchange.create_order.return_value = {
            "id": "order456",
            "type": "limit",
            "price": 67000.0,
        }
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        result = client.create_order(
            symbol="BTC/USDT:USDT",
            order_type="limit",
            side="sell",
            amount=0.015,
            price=67000.0,
        )

        assert result["type"] == "limit"
        mock_exchange.create_order.assert_called_once()


class TestFetchBalance:
    """Test fetch_balance functionality."""

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_returns_usdt_balance(self, mock_ccxt):
        """Should return USDT balance."""
        mock_exchange = MagicMock()
        mock_exchange.fetch_balance.return_value = {
            "USDT": {"free": 10000.0, "used": 0.0, "total": 10000.0},
        }
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        result = client.fetch_balance()

        assert result["USDT"]["total"] == 10000.0


class TestSetLeverage:
    """Test set_leverage functionality."""

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_sets_leverage(self, mock_ccxt):
        """Should set leverage for symbol."""
        mock_exchange = MagicMock()
        mock_exchange.set_leverage.return_value = {"leverage": 2}
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        result = client.set_leverage(2, "BTC/USDT:USDT")

        assert result["leverage"] == 2


class TestFetchPositions:
    """Test fetch_positions functionality."""

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_returns_open_positions(self, mock_ccxt, mock_position):
        """Should return list of open positions."""
        mock_exchange = MagicMock()
        mock_exchange.fetch_positions.return_value = [mock_position]
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        result = client.fetch_positions()

        assert len(result) == 1
        assert result[0]["symbol"] == "BTC/USDT:USDT"

    @patch("newtrade.binance_ta_bot.core.exchange_client.ccxt")
    def test_returns_empty_when_no_positions(self, mock_ccxt):
        """Should return empty list when no positions."""
        mock_exchange = MagicMock()
        mock_exchange.fetch_positions.return_value = []
        mock_ccxt.binanceusdm.return_value = mock_exchange

        from newtrade.binance_ta_bot.core.exchange_client import (
            ExchangeClient,
        )
        client = ExchangeClient(
            exchange_name="binanceusdm",
            api_key="test_key",
            api_secret="test_secret",
        )
        result = client.fetch_positions()

        assert result == []
