"""TDD tests for StateManager - written BEFORE implementation."""

import json
import os
import pytest
from unittest.mock import patch
from datetime import datetime, timezone


@pytest.fixture
def state_file(tmp_path):
    """Temporary state file path."""
    return str(tmp_path / "state_ta_bot.json")


@pytest.fixture
def sample_state():
    """Sample bot state."""
    return {
        "bot_status": "running",
        "equity": 10000.0,
        "daily_pnl": -5.23,
        "daily_trades": 2,
        "open_positions": [
            {
                "symbol": "BTC/USDT:USDT",
                "side": "long",
                "entry_price": 67500.0,
                "size": 0.015,
                "stop_loss": 67000.0,
                "take_profit": 68500.0,
                "entry_time": "2026-03-28T10:30:00Z",
            }
        ],
        "last_scan": "2026-03-28T12:00:00Z",
    }


class TestStateManagerInit:
    """Test StateManager initialization."""

    def test_creates_state_manager(self, state_file):
        """Should create state manager with file path."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        assert manager.state_file == state_file

    def test_creates_default_state_when_no_file(self, state_file):
        """Should create default state when file doesn't exist."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        state = manager.load()

        assert state["bot_status"] == "idle"
        assert state["equity"] == 0.0
        assert state["open_positions"] == []
        assert state["daily_trades"] == 0


class TestSaveLoad:
    """Test save and load functionality."""

    def test_saves_state_to_file(self, state_file, sample_state):
        """Should persist state to JSON file."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        manager.save(sample_state)

        assert os.path.exists(state_file)
        with open(state_file) as f:
            saved = json.load(f)
        assert saved["equity"] == 10000.0

    def test_loads_state_from_file(self, state_file, sample_state):
        """Should load state from JSON file."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        manager.save(sample_state)

        loaded = manager.load()
        assert loaded["equity"] == 10000.0
        assert len(loaded["open_positions"]) == 1

    def test_preserves_position_data(self, state_file, sample_state):
        """Should preserve all position fields."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        manager.save(sample_state)
        loaded = manager.load()

        pos = loaded["open_positions"][0]
        assert pos["symbol"] == "BTC/USDT:USDT"
        assert pos["side"] == "long"
        assert pos["entry_price"] == 67500.0
        assert pos["stop_loss"] == 67000.0
        assert pos["take_profit"] == 68500.0


class TestPositionManagement:
    """Test position add/remove."""

    def test_add_position(self, state_file):
        """Should add position to state."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        manager.load()

        position = {
            "symbol": "ETH/USDT:USDT",
            "side": "short",
            "entry_price": 3500.0,
            "size": 0.5,
            "stop_loss": 3600.0,
            "take_profit": 3300.0,
            "entry_time": "2026-03-28T14:00:00Z",
        }
        manager.add_position(position)

        state = manager.load()
        assert len(state["open_positions"]) == 1
        assert state["open_positions"][0]["symbol"] == "ETH/USDT:USDT"

    def test_remove_position(self, state_file):
        """Should remove position from state."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        manager.load()

        position = {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "entry_price": 67500.0,
            "size": 0.015,
            "stop_loss": 67000.0,
            "take_profit": 68500.0,
            "entry_time": "2026-03-28T10:30:00Z",
        }
        manager.add_position(position)
        manager.remove_position("BTC/USDT:USDT")

        state = manager.load()
        assert len(state["open_positions"]) == 0

    def test_get_position_by_symbol(self, state_file):
        """Should find position by symbol."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        manager.load()

        position = {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "entry_price": 67500.0,
            "size": 0.015,
            "stop_loss": 67000.0,
            "take_profit": 68500.0,
            "entry_time": "2026-03-28T10:30:00Z",
        }
        manager.add_position(position)

        found = manager.get_position("BTC/USDT:USDT")
        assert found is not None
        assert found["entry_price"] == 67500.0

    def test_get_position_returns_none_when_not_found(self, state_file):
        """Should return None for non-existent symbol."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        manager.load()

        found = manager.get_position("DOGE/USDT:USDT")
        assert found is None


class TestDailyStats:
    """Test daily statistics tracking."""

    def test_update_daily_pnl(self, state_file):
        """Should update daily PnL."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        manager.load()

        manager.update_daily_pnl(-5.23)
        state = manager.load()
        assert state["daily_pnl"] == -5.23

    def test_increment_daily_trades(self, state_file):
        """Should increment trade counter."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        manager.load()

        manager.increment_daily_trades()
        manager.increment_daily_trades()
        state = manager.load()
        assert state["daily_trades"] == 2

    def test_reset_daily_stats(self, state_file):
        """Should reset daily stats."""
        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        manager.load()

        manager.update_daily_pnl(-10.0)
        manager.increment_daily_trades()
        manager.increment_daily_trades()
        manager.reset_daily_stats()

        state = manager.load()
        assert state["daily_pnl"] == 0.0
        assert state["daily_trades"] == 0


class TestCrashRecovery:
    """Test crash recovery behavior."""

    def test_corrupted_file_creates_default(self, state_file):
        """Should create default state on corrupted file."""
        with open(state_file, "w") as f:
            f.write("{corrupted json!!")

        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        state = manager.load()

        assert state["bot_status"] == "idle"
        assert state["open_positions"] == []

    def test_empty_file_creates_default(self, state_file):
        """Should create default state on empty file."""
        with open(state_file, "w") as f:
            f.write("")

        from newtrade.binance_ta_bot.core.state_manager import (
            StateManager,
        )
        manager = StateManager(state_file=state_file)
        state = manager.load()

        assert state["bot_status"] == "idle"
