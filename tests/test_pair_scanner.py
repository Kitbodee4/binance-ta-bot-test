"""TDD tests for PairScanner - written BEFORE implementation."""

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Pure-function helpers (tested independently)
# ---------------------------------------------------------------------------

SAMPLE_MARKETS = [
    {"symbol": "BTC/USDT:USDT", "quoteVolume": 500_000_000},
    {"symbol": "ETH/USDT:USDT", "quoteVolume": 200_000_000},
    {"symbol": "SOL/USDT:USDT", "quoteVolume": 50_000_000},
    {"symbol": "DOGE/USDT:USDT", "quoteVolume": 8_000_000},   # below 10M
    {"symbol": "USDC/USDT:USDT", "quoteVolume": 300_000_000},  # stablecoin
    {"symbol": "BTCUP/USDT:USDT", "quoteVolume": 100_000_000}, # leveraged
    {"symbol": "BTCDOWN/USDT:USDT", "quoteVolume": 50_000_000},# leveraged
    {"symbol": "BUSD/USDT:USDT", "quoteVolume": 90_000_000},   # stablecoin
    {"symbol": "XRP/USDT:USDT", "quoteVolume": 15_000_000},
    {"symbol": "ADA/USDT:USDT", "quoteVolume": 12_000_000},
]


class TestFilterByVolume:
    """filter_by_volume(markets, min_volume) keeps only markets >= threshold."""

    def test_filters_below_threshold(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            filter_by_volume,
        )
        result = filter_by_volume(SAMPLE_MARKETS, min_volume=10_000_000)
        symbols = [m["symbol"] for m in result]
        assert "DOGE/USDT:USDT" not in symbols  # 8M < 10M

    def test_keeps_above_threshold(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            filter_by_volume,
        )
        result = filter_by_volume(SAMPLE_MARKETS, min_volume=10_000_000)
        symbols = [m["symbol"] for m in result]
        assert "BTC/USDT:USDT" in symbols
        assert "ETH/USDT:USDT" in symbols

    def test_keeps_exact_threshold(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            filter_by_volume,
        )
        markets = [{"symbol": "FOO/USDT:USDT", "quoteVolume": 10_000_000}]
        result = filter_by_volume(markets, min_volume=10_000_000)
        assert len(result) == 1

    def test_empty_input(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            filter_by_volume,
        )
        assert filter_by_volume([], min_volume=10_000_000) == []


class TestExcludePatterns:
    """exclude_patterns(markets, patterns) removes matching symbols."""

    def test_excludes_usdc(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            exclude_patterns,
        )
        result = exclude_patterns(SAMPLE_MARKETS, ["USDC"])
        symbols = [m["symbol"] for m in result]
        assert "USDC/USDT:USDT" not in symbols

    def test_excludes_busd(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            exclude_patterns,
        )
        result = exclude_patterns(SAMPLE_MARKETS, ["BUSD"])
        symbols = [m["symbol"] for m in result]
        assert "BUSD/USDT:USDT" not in symbols

    def test_excludes_leveraged_up(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            exclude_patterns,
        )
        result = exclude_patterns(SAMPLE_MARKETS, ["UP/", "DOWN/"])
        symbols = [m["symbol"] for m in result]
        assert "BTCUP/USDT:USDT" not in symbols
        assert "BTCDOWN/USDT:USDT" not in symbols

    def test_keeps_normal_pairs(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            exclude_patterns,
        )
        result = exclude_patterns(
            SAMPLE_MARKETS, ["USDC", "BUSD", "UP/", "DOWN/"],
        )
        symbols = [m["symbol"] for m in result]
        assert "BTC/USDT:USDT" in symbols
        assert "ETH/USDT:USDT" in symbols
        assert "SOL/USDT:USDT" in symbols

    def test_empty_patterns_keeps_all(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            exclude_patterns,
        )
        result = exclude_patterns(SAMPLE_MARKETS, [])
        assert len(result) == len(SAMPLE_MARKETS)

    def test_empty_input(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            exclude_patterns,
        )
        assert exclude_patterns([], ["USDC"]) == []


class TestSortByVolume:
    """sort_by_volume(markets) returns descending by 24h volume."""

    def test_sorted_descending(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            sort_by_volume,
        )
        result = sort_by_volume(SAMPLE_MARKETS)
        volumes = [m["quoteVolume"] for m in result]
        assert volumes == sorted(volumes, reverse=True)

    def test_btc_is_first(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            sort_by_volume,
        )
        result = sort_by_volume(SAMPLE_MARKETS)
        assert result[0]["symbol"] == "BTC/USDT:USDT"

    def test_empty_input(self):
        from newtrade.binance_ta_bot.scanner.pair_scanner import (
            sort_by_volume,
        )
        assert sort_by_volume([]) == []


class TestPairScannerClass:
    """PairScanner orchestration with mock exchange."""

    @pytest.fixture
    def mock_exchange(self):
        """Mock exchange with fetch_tickers returning test data."""
        tickers_list = [
            {
                "symbol": "BTC/USDT:USDT",
                "quoteVolume": 500_000_000,
                "type": "swap",
            },
            {
                "symbol": "ETH/USDT:USDT",
                "quoteVolume": 200_000_000,
                "type": "swap",
            },
            {
                "symbol": "SOL/USDT:USDT",
                "quoteVolume": 50_000_000,
                "type": "swap",
            },
            {
                "symbol": "USDC/USDT:USDT",
                "quoteVolume": 300_000_000,
                "type": "swap",
            },
            {
                "symbol": "BTCUP/USDT:USDT",
                "quoteVolume": 100_000_000,
                "type": "swap",
            },
            {
                "symbol": "DOGE/USDT:USDT",
                "quoteVolume": 8_000_000,
                "type": "swap",
            },
            {
                "symbol": "XRP/USDT:USDT",
                "quoteVolume": 15_000_000,
                "type": "swap",
            },
        ]
        exchange = MagicMock()
        exchange.fetch_tickers.return_value = {
            t["symbol"]: t for t in tickers_list
        }
        return exchange

    def test_returns_list_of_strings(self, mock_exchange):
        """scan() returns list of symbol strings."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(exchange_client=mock_exchange)
        result = scanner.scan()
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_excludes_stablecoins(self, mock_exchange):
        """scan() excludes stablecoin pairs."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(exchange_client=mock_exchange)
        result = scanner.scan()
        assert "USDC/USDT:USDT" not in result

    def test_excludes_leveraged(self, mock_exchange):
        """scan() excludes leveraged token pairs."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(exchange_client=mock_exchange)
        result = scanner.scan()
        assert "BTCUP/USDT:USDT" not in result

    def test_excludes_low_volume(self, mock_exchange):
        """scan() excludes pairs below min volume threshold."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(
            exchange_client=mock_exchange,
            min_volume_usd=10_000_000,
        )
        result = scanner.scan()
        assert "DOGE/USDT:USDT" not in result

    def test_respects_top_n(self, mock_exchange):
        """scan() returns at most top_n pairs."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(exchange_client=mock_exchange, top_n=2)
        result = scanner.scan()
        assert len(result) == 2

    def test_sorted_by_volume_desc(self, mock_exchange):
        """scan() results are sorted by volume descending."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(exchange_client=mock_exchange)
        result = scanner.scan()
        assert result[0] == "BTC/USDT:USDT"
        assert result[1] == "ETH/USDT:USDT"

    def test_custom_exclude_patterns(self, mock_exchange):
        """scan() respects custom exclude patterns."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(
            exchange_client=mock_exchange,
            exclude_patterns=["BTC"],
        )
        result = scanner.scan()
        assert "BTC/USDT:USDT" not in result

    def test_custom_min_volume(self, mock_exchange):
        """scan() respects custom min volume threshold."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(
            exchange_client=mock_exchange,
            min_volume_usd=1_000_000_000,
        )
        result = scanner.scan()
        # Only BTC has 500M, which is below 1B threshold
        assert result == []

    def test_default_exclude_patterns(self, mock_exchange):
        """Default exclude patterns are USDC, BUSD, UP/, DOWN/."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(exchange_client=mock_exchange)
        assert "USDC" in scanner.exclude_patterns
        assert "BUSD" in scanner.exclude_patterns
        assert "UP/" in scanner.exclude_patterns
        assert "DOWN/" in scanner.exclude_patterns


class TestScanIntegration:
    """Full integration: fetch -> filter -> exclude -> sort -> top N."""

    @pytest.fixture
    def realistic_exchange(self):
        """Mock exchange with realistic 25-pair dataset."""
        pairs = [
            ("BTC/USDT:USDT", 800_000_000),
            ("ETH/USDT:USDT", 400_000_000),
            ("SOL/USDT:USDT", 150_000_000),
            ("XRP/USDT:USDT", 120_000_000),
            ("ADA/USDT:USDT", 90_000_000),
            ("DOGE/USDT:USDT", 80_000_000),
            ("AVAX/USDT:USDT", 70_000_000),
            ("DOT/USDT:USDT", 60_000_000),
            ("MATIC/USDT:USDT", 55_000_000),
            ("LINK/USDT:USDT", 50_000_000),
            ("UNI/USDT:USDT", 45_000_000),
            ("ATOM/USDT:USDT", 40_000_000),
            ("FIL/USDT:USDT", 35_000_000),
            ("APT/USDT:USDT", 30_000_000),
            ("ARB/USDT:USDT", 28_000_000),
            ("OP/USDT:USDT", 25_000_000),
            ("NEAR/USDT:USDT", 22_000_000),
            ("INJ/USDT:USDT", 20_000_000),
            ("SUI/USDT:USDT", 18_000_000),
            ("SEI/USDT:USDT", 15_000_000),
            ("TIA/USDT:USDT", 12_000_000),
            # These should be excluded
            ("USDC/USDT:USDT", 300_000_000),
            ("BTCUP/USDT:USDT", 100_000_000),
            ("BTCDOWN/USDT:USDT", 50_000_000),
            ("BUSD/USDT:USDT", 90_000_000),
            # Below volume threshold
            ("LOWVOL/USDT:USDT", 5_000_000),
        ]
        tickers_dict = {
            s: {"symbol": s, "quoteVolume": v, "type": "swap"}
            for s, v in pairs
        }
        exchange = MagicMock()
        exchange.fetch_tickers.return_value = tickers_dict
        return exchange

    def test_full_scan_returns_20(self, realistic_exchange):
        """Full scan with top_n=20 returns exactly 20 pairs."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(
            exchange_client=realistic_exchange, top_n=20,
        )
        result = scanner.scan()
        assert len(result) == 20

    def test_full_scan_excludes_unwanted(self, realistic_exchange):
        """Full scan excludes stablecoins, leveraged, low volume."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(
            exchange_client=realistic_exchange, top_n=20,
        )
        result = scanner.scan()
        excluded = {"USDC/USDT:USDT", "BTCUP/USDT:USDT",
                    "BTCDOWN/USDT:USDT", "BUSD/USDT:USDT", "LOWVOL/USDT:USDT"}
        for sym in excluded:
            assert sym not in result

    def test_full_scan_sorted(self, realistic_exchange):
        """Full scan results are sorted by volume descending."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(
            exchange_client=realistic_exchange, top_n=20,
        )
        result = scanner.scan()
        assert result[0] == "BTC/USDT:USDT"
        assert result[1] == "ETH/USDT:USDT"
        # 21 pairs qualify, top_n=20 → TIA (12M) is cut; SEI (15M) is last
        assert result[-1] == "SEI/USDT:USDT"
        assert "TIA/USDT:USDT" not in result

    def test_top_n_5_returns_btc_through_avax(self, realistic_exchange):
        """top_n=5 returns the 5 highest-volume pairs."""
        from newtrade.binance_ta_bot.scanner.pair_scanner import PairScanner
        scanner = PairScanner(
            exchange_client=realistic_exchange, top_n=5,
        )
        result = scanner.scan()
        assert len(result) == 5
        assert result == [
            "BTC/USDT:USDT",
            "ETH/USDT:USDT",
            "SOL/USDT:USDT",
            "XRP/USDT:USDT",
            "ADA/USDT:USDT",
        ]
