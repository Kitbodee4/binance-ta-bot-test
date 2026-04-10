"""Auto-scan for high-volume trading pairs."""

from loguru import logger


# ---------------------------------------------------------------------------
# Pure-function helpers
# ---------------------------------------------------------------------------

def filter_by_volume(
    markets: list[dict],
    min_volume: float,
) -> list[dict]:
    """Keep only markets whose ``quoteVolume`` >= *min_volume*."""
    return [m for m in markets if m.get("quoteVolume", 0) >= min_volume]


def exclude_patterns(
    markets: list[dict],
    patterns: list[str],
) -> list[dict]:
    """Remove markets whose symbol contains any of *patterns*."""
    if not patterns:
        return list(markets)
    return [
        m for m in markets
        if not any(p in m.get("symbol", "") for p in patterns)
    ]


def sort_by_volume(markets: list[dict]) -> list[dict]:
    """Sort markets by ``quoteVolume`` descending."""
    return sorted(markets, key=lambda m: m.get("quoteVolume", 0), reverse=True)


# ---------------------------------------------------------------------------
# Scanner class
# ---------------------------------------------------------------------------

class PairScanner:
    """Scans exchange for top trading pairs by volume.

    Parameters
    ----------
    exchange_client : ccxt-compatible exchange instance
        Must expose ``fetch_tickers()``.
    top_n : int
        Maximum number of symbols to return (default 20).
    min_volume_usd : float
        Minimum 24 h quote volume in USD (default $10 M).
    exclude_patterns : list[str] | None
        Substrings that disqualify a symbol.  Defaults to
        ``["USDC", "BUSD", "UP/", "DOWN/"]``.
    """

    def __init__(
        self,
        exchange_client,
        top_n: int = 20,
        min_volume_usd: float = 1_000_000,
        exclude_patterns: list[str] | None = None,
    ):
        self.exchange = exchange_client
        self.top_n = top_n
        self.min_volume_usd = min_volume_usd
        self.exclude_patterns = exclude_patterns or [
            "USDC", "BUSD", "UP/", "DOWN/",
        ]

    def scan(self) -> list[str]:
        """Scan for top pairs by volume.

        Returns
        -------
        list[str]
            Symbol strings sorted by 24 h volume descending, limited to
            *top_n* entries.
        """
        # 1. Fetch tickers (has quoteVolume, unlike fetch_markets)
        logger.info("Fetching tickers from exchange...")
        tickers = self.exchange.fetch_tickers()
        raw_markets = list(tickers.values())
        logger.info(f"Fetched {len(raw_markets)} tickers")

        # 2. Filter by volume
        markets = filter_by_volume(raw_markets, self.min_volume_usd)
        logger.info(f"After volume filter (>=${self.min_volume_usd:,.0f}): {len(markets)}")

        # 3. Exclude patterns
        markets = exclude_patterns(markets, self.exclude_patterns)
        logger.info(f"After exclude patterns: {len(markets)}")

        # 4. Sort by volume descending
        markets = sort_by_volume(markets)

        # 5. Return top N symbols
        result = [m["symbol"] for m in markets[: self.top_n]]
        logger.info(f"Selected top {len(result)} pairs: {result}")
        return result
