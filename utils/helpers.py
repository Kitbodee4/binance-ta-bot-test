"""Shared utility functions for Binance TA bot."""

from typing import Any


def load_yaml_config(path: str) -> dict[str, Any]:
    """Load YAML configuration file.

    Args:
        path: Path to YAML config file.

    Returns:
        Parsed configuration as dict.
    """
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float.

    Args:
        value: Value to convert.
        default: Default if conversion fails.

    Returns:
        Float value or default.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def truncate_float(value: float, decimals: int = 8) -> float:
    """Truncate float to specified decimal places (no rounding).

    Args:
        value: Float value to truncate.
        decimals: Number of decimal places.

    Returns:
        Truncated float.
    """
    factor = 10 ** decimals
    return int(value * factor) / factor
