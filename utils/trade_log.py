"""Trade journal logger — records every entry/exit to CSV."""

import csv
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


TRADE_LOG_PATH = Path("trades.csv")

HEADERS = [
    "timestamp",
    "symbol",
    "side",
    "entry_price",
    "close_price",
    "size",
    "stop_loss",
    "take_profit",
    "pnl",
    "pnl_pct",
    "reason",
]


def init_trade_log(path: Path = TRADE_LOG_PATH) -> None:
    """Create CSV with headers if not exists."""
    if not path.exists():
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS)
        logger.info(f"Trade log created: {path}")


def log_entry(
    symbol: str,
    side: str,
    entry_price: float,
    size: float,
    stop_loss: float,
    take_profit: float,
    path: Path = TRADE_LOG_PATH,
) -> None:
    """Log a trade entry (exit fields left blank)."""
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            symbol,
            side,
            f"{entry_price:.6f}",
            "",  # close_price — filled on exit
            f"{size:.6f}",
            f"{stop_loss:.6f}",
            f"{take_profit:.6f}",
            "",  # pnl
            "",  # pnl_pct
            "OPEN",
        ])
    logger.info(f"Trade logged: {side} {symbol} @ {entry_price}")


def log_exit(
    symbol: str,
    side: str,
    entry_price: float,
    close_price: float,
    size: float,
    stop_loss: float,
    take_profit: float,
    reason: str,
    path: Path = TRADE_LOG_PATH,
) -> None:
    """Log a trade exit with PnL calculation."""
    if side == "long":
        pnl = (close_price - entry_price) * size
        pnl_pct = (close_price - entry_price) / entry_price
    else:
        pnl = (entry_price - close_price) * size
        pnl_pct = (entry_price - close_price) / entry_price

    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            symbol,
            side,
            f"{entry_price:.6f}",
            f"{close_price:.6f}",
            f"{size:.6f}",
            f"{stop_loss:.6f}",
            f"{take_profit:.6f}",
            f"{pnl:.4f}",
            f"{pnl_pct:.4%}",
            reason,
        ])

    emoji = "🟢" if pnl >= 0 else "🔴"
    logger.info(
        f"{emoji} Trade closed: {side} {symbol} "
        f"entry={entry_price:.4f} close={close_price:.4f} "
        f"pnl={pnl:.4f} ({pnl_pct:.2%}) reason={reason}"
    )
