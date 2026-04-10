"""StateManager - JSON-based state persistence for Binance TA Bot."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger


DEFAULT_STATE: Dict[str, Any] = {
    "bot_status": "idle",
    "equity": 0.0,
    "daily_pnl": 0.0,
    "daily_trades": 0,
    "open_positions": [],
    "last_scan": None,
}


class StateManager:
    """Manages bot state persistence via JSON file."""

    def __init__(self, state_file: str) -> None:
        self.state_file = state_file
        self._state: Dict[str, Any] = {}

    def _default_state(self) -> Dict[str, Any]:
        """Return a fresh copy of default state."""
        return {k: (list(v) if isinstance(v, list) else v)
                for k, v in DEFAULT_STATE.items()}

    def load(self) -> Dict[str, Any]:
        """Load state from JSON file.

        Returns default state if file is missing, empty, or corrupted.
        """
        path = Path(self.state_file)
        if not path.exists():
            logger.info(f"State file not found: {self.state_file}, using defaults")
            self._state = self._default_state()
            return self._state

        try:
            with open(path) as f:
                content = f.read().strip()
                if not content:
                    logger.warning(f"State file empty: {self.state_file}, using defaults")
                    self._state = self._default_state()
                    return self._state
                self._state = json.loads(content)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Corrupted state file: {e}, using defaults")
            self._state = self._default_state()

        return self._state

    def save(self, state: Dict[str, Any]) -> None:
        """Save state dict to JSON file."""
        self._state = state
        path = Path(self.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        logger.debug(f"State saved to {self.state_file}")

    def add_position(self, position: Dict[str, Any]) -> None:
        """Append a position to open_positions and save."""
        self._state.setdefault("open_positions", []).append(position)
        self.save(self._state)

    def remove_position(self, symbol: str) -> None:
        """Remove a position by symbol from open_positions and save."""
        positions = self._state.get("open_positions", [])
        self._state["open_positions"] = [
            p for p in positions if p.get("symbol") != symbol
        ]
        self.save(self._state)

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Return position dict for symbol, or None."""
        for pos in self._state.get("open_positions", []):
            if pos.get("symbol") == symbol:
                return pos
        return None

    def update_daily_pnl(self, value: float) -> None:
        """Set daily_pnl to value and save."""
        self._state["daily_pnl"] = value
        self.save(self._state)

    def increment_daily_trades(self) -> None:
        """Increment daily_trades by 1 and save."""
        self._state["daily_trades"] = self._state.get("daily_trades", 0) + 1
        self.save(self._state)

    def reset_daily_stats(self) -> None:
        """Reset daily_pnl and daily_trades to defaults and save."""
        self._state["daily_pnl"] = 0.0
        self._state["daily_trades"] = 0
        self.save(self._state)
    def update_full_state(self, equity: float, daily_pnl: float, positions: list) -> None:
        """Update all tracked fields and save."""
        self._state["equity"] = equity
        self._state["daily_pnl"] = daily_pnl
        self._state["open_positions"] = list(positions)
        self.save(self._state)
