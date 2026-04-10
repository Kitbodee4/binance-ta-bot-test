"""Shared test fixtures for Binance TA bot tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


@pytest.fixture
def mock_ticker():
    """Mock ticker response from CCXT."""
    return {
        "symbol": "BTC/USDT:USDT",
        "last": 67500.0,
        "bid": 67499.0,
        "ask": 67501.0,
        "high": 68000.0,
        "low": 66500.0,
        "volume": 15000.0,
        "timestamp": 1711603200000,
    }


@pytest.fixture
def mock_ohlcv_15m():
    """Mock 15m OHLCV data (20 candles)."""
    candles = []
    base_price = 67000.0
    for i in range(20):
        candles.append([
            1711603200000 + i * 900000,  # timestamp
            base_price + i * 10,          # open
            base_price + i * 10 + 50,     # high
            base_price + i * 10 - 30,     # low
            base_price + i * 10 + 20,     # close
            1000.0 + i * 50,              # volume
        ])
    return candles


@pytest.fixture
def mock_ohlcv_1h():
    """Mock 1h OHLCV data (50 candles)."""
    candles = []
    base_price = 66000.0
    for i in range(50):
        candles.append([
            1711603200000 + i * 3600000,
            base_price + i * 20,
            base_price + i * 20 + 100,
            base_price + i * 20 - 80,
            base_price + i * 20 + 15,
            5000.0 + i * 100,
        ])
    return candles


@pytest.fixture
def mock_balance():
    """Mock account balance response."""
    return {
        "USDT": {
            "free": 10000.0,
            "used": 0.0,
            "total": 10000.0,
        },
        "info": {},
    }


@pytest.fixture
def mock_position():
    """Mock open position response."""
    return {
        "symbol": "BTC/USDT:USDT",
        "side": "long",
        "contracts": 0.015,
        "entryPrice": 67500.0,
        "markPrice": 67600.0,
        "unrealizedPnl": 1.5,
        "leverage": 2.0,
        "liquidationPrice": 33750.0,
        "timestamp": 1711603200000,
    }


@pytest.fixture
def mock_exchange():
    """Mock CCXT exchange instance."""
    exchange = MagicMock()
    exchange.fetch_ticker = MagicMock(return_value={
        "symbol": "BTC/USDT:USDT",
        "last": 67500.0,
        "bid": 67499.0,
        "ask": 67501.0,
        "volume": 15000.0,
        "timestamp": 1711603200000,
    })
    exchange.fetch_ohlcv = MagicMock(return_value=[
        [1711603200000, 67000, 67500, 66500, 67400, 1000],
        [1711604100000, 67400, 67600, 67300, 67500, 1100],
    ])
    exchange.fetch_balance = MagicMock(return_value={
        "USDT": {"free": 10000.0, "used": 0.0, "total": 10000.0},
    })
    exchange.create_order = MagicMock(return_value={
        "id": "order123",
        "symbol": "BTC/USDT:USDT",
        "type": "market",
        "side": "buy",
        "amount": 0.015,
        "price": 67500.0,
        "status": "closed",
        "filled": 0.015,
    })
    exchange.fetch_positions = MagicMock(return_value=[])
    exchange.set_leverage = MagicMock(return_value={"leverage": 2})
    return exchange


@pytest.fixture
def sample_config():
    """Sample configuration dict."""
    return {
        "exchange": {
            "name": "binanceusdm",
            "sandbox": False,
        },
        "strategy": {
            "ema_fast": 9,
            "ema_slow": 21,
            "rsi_period": 14,
        },
        "risk": {
            "risk_per_trade": 0.01,
            "max_leverage": 3,
            "max_positions": 3,
        },
        "bot": {
            "scan_interval_sec": 60,
            "dry_run": True,
            "log_level": "INFO",
        },
    }
