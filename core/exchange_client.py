"""CCXT exchange client wrapper with retry and dry-run support."""

import ccxt
from ccxt import NetworkError as _NetworkError
from loguru import logger


class ExchangeClient:
    """Wrapper around CCXT exchange with retry logic and dry-run mode."""

    def __init__(
        self,
        exchange_name: str,
        api_key: str,
        api_secret: str,
        dry_run: bool = False,
    ) -> None:
        self.exchange_name = exchange_name
        self.dry_run = dry_run

        exchange_class = getattr(ccxt, exchange_name)
        self.exchange = exchange_class({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        })
        logger.info(
            f"ExchangeClient initialized: {exchange_name} "
            f"(dry_run={dry_run})"
        )

    def fetch_ticker(self, symbol: str) -> dict:
        """Fetch ticker data, retry once on NetworkError."""
        try:
            return self.exchange.fetch_ticker(symbol)
        except _NetworkError as e:
            logger.warning(
                f"NetworkError fetching ticker {symbol}: {e}, retrying"
            )
            return self.exchange.fetch_ticker(symbol)

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int | None = None
    ) -> list:
        """Fetch OHLCV candles."""
        kwargs: dict = {"timeframe": timeframe}
        if limit is not None:
            kwargs["limit"] = limit
        return self.exchange.fetch_ohlcv(symbol, **kwargs)

    def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float | None = None,
    ) -> dict:
        """Place order; returns simulated response in dry-run mode."""
        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would place {order_type} {side} "
                f"{amount} {symbol}"
            )
            return {"dry_run": True}

        kwargs: dict = {}
        if price is not None:
            kwargs["price"] = price
        return self.exchange.create_order(
            symbol, order_type, side, amount, **kwargs
        )

    def fetch_balance(self) -> dict:
        """Fetch account balance."""
        return self.exchange.fetch_balance()

    def set_leverage(self, leverage: int, symbol: str) -> dict:
        """Set leverage for a symbol."""
        return self.exchange.set_leverage(leverage, symbol)

    def fetch_positions(self) -> list:
        """Fetch open positions."""
        return self.exchange.fetch_positions()

    def fetch_markets(self) -> list:
        """Fetch available markets from the exchange."""
        return self.exchange.fetch_markets()

    def fetch_tickers(self) -> dict:
        """Fetch all tickers (includes quoteVolume, bid, ask, etc.)."""
        return self.exchange.fetch_tickers()

    def fetch_order(self, order_id: str, symbol: str) -> dict:
        """Fetch order status by ID and symbol.

        Args:
            order_id: The order ID to look up.
            symbol: Trading pair symbol (e.g. 'BTC/USDT:USDT').

        Returns:
            Order dict from the exchange.
        """
        return self.exchange.fetch_order(order_id, symbol)

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Cancel an open order by ID and symbol.

        Args:
            order_id: The order ID to cancel.
            symbol: Trading pair symbol (e.g. 'BTC/USDT:USDT').

        Returns:
            Cancellation result dict from the exchange.
        """
        return self.exchange.cancel_order(order_id, symbol)
