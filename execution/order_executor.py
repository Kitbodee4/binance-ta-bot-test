"""Order execution with partial fill tracking."""

import random
import time
from typing import Any, Dict

from loguru import logger


class OrderExecutor:
    """Execute orders with circuit breaker, slippage control, and partial fill handling.

    Supports dry-run (paper trade) mode for testing without real exchange calls.

    Args:
        exchange_client: CCXT exchange client instance.
        circuit_breaker: CircuitBreaker for halt/slippage/flash-crash checks.
        max_slippage_pct: Maximum acceptable slippage as a fraction (e.g., 0.001 = 0.1%).
        order_timeout_sec: Timeout in seconds for partial fill polling.
        dry_run: If True, simulate fills instead of placing real orders.
    """

    def __init__(
        self,
        exchange_client: Any,
        circuit_breaker: Any,
        max_slippage_pct: float = 0.001,
        order_timeout_sec: int = 30,
        dry_run: bool = True,
    ) -> None:
        self.exchange_client = exchange_client
        self.circuit_breaker = circuit_breaker
        self.max_slippage_pct = max_slippage_pct
        self.order_timeout_sec = order_timeout_sec
        self.dry_run = dry_run

    def execute_entry(
        self,
        symbol: str,
        side: str,
        size: float,
        intended_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> Dict[str, Any]:
        """Place market entry + SL/TP. Returns order result dict.

        In dry_run mode:
            Return simulated fill dict with slippage within max_slippage_pct bounds.
            Does NOT call exchange.create_order.

        In live mode:
            1. Check circuit_breaker.should_halt()
            2. Place market order via exchange
            3. Check slippage via circuit_breaker
            4. Handle partial fills with polling
            5. Place SL and TP orders sized to actual fill

        Args:
            symbol: Trading pair (e.g., "BTC/USDT:USDT").
            side: "buy" for long, "sell" for short.
            size: Order size in contracts/coins.
            intended_price: Expected fill price for slippage calculation.
            stop_loss: Stop-loss trigger price.
            take_profit: Take-profit trigger price.

        Returns:
            Dict with order result including id, status, filled, avg_price, etc.
        """
        # Validate size
        if size <= 0:
            logger.warning(f"Rejected order: size={size} is not positive")
            return {"rejected": True, "status": "rejected", "reason": "invalid_size"}

        # Dry-run mode
        if self.dry_run:
            return self._execute_entry_dry_run(
                symbol, side, size, intended_price, stop_loss, take_profit
            )

        # Live mode: circuit breaker halt check
        if self.circuit_breaker.should_halt():
            logger.warning("Order rejected: circuit breaker halt")
            return {
                "rejected": True,
                "reason": "circuit_breaker_halt",
                "status": "rejected",
            }

        # Validate intended_price for live mode
        if intended_price <= 0:
            logger.warning(
                f"Rejected order: intended_price={intended_price} is invalid"
            )
            return {"rejected": True, "status": "rejected", "reason": "invalid_price"}

        # Place market entry order
        try:
            order = self.exchange_client.create_order(
                symbol, "market", side, size
            )
        except Exception as e:
            logger.error(f"Failed to create entry order: {e}")
            return {"error": str(e), "status": "error"}

        order_id = order.get("id", "")
        status = order.get("status", "unknown")
        filled = order.get("filled", 0) or 0
        avg_price = order.get("average") or order.get("price") or intended_price

        # Calculate slippage
        slippage_pct = abs(avg_price - intended_price) / intended_price

        # Check slippage via circuit breaker
        if not self.circuit_breaker.check_slippage(intended_price, avg_price):
            logger.warning(
                f"Order rejected: slippage {slippage_pct:.4%} exceeds limit"
            )
            return {
                "rejected": True,
                "status": "rejected",
                "id": order_id,
                "slippage_pct": slippage_pct,
                "avg_price": avg_price,
            }

        # Handle partial fills
        if status == "open" and filled < size:
            filled = self._handle_partial_fill(order_id, symbol, filled, size)

        # Log fill ratio for backtest comparison
        fill_ratio = filled / size if size > 0 else 0
        logger.info(
            f"Fill ratio: {filled}/{size} = {fill_ratio:.2%} "
            f"for {symbol} {side}"
        )

        # Place SL and TP sized to actual fill (using internal methods)
        sl_order: Dict[str, Any] = {}
        tp_order: Dict[str, Any] = {}

        if filled > 0:
            sl_order = self._place_stop_loss_internal(
                symbol, side, filled, stop_loss
            )
            tp_order = self._place_take_profit_internal(
                symbol, side, filled, take_profit
            )

        result: Dict[str, Any] = {
            "id": order_id,
            "status": status if filled >= size * 0.5 else "partial",
            "filled": filled,
            "avg_price": avg_price,
            "slippage_pct": slippage_pct,
            "sl_order_id": sl_order.get("id", ""),
            "tp_order_id": tp_order.get("id", ""),
        }
        return result

    def _execute_entry_dry_run(
        self,
        symbol: str,
        side: str,
        size: float,
        intended_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> Dict[str, Any]:
        """Simulate an entry fill in dry-run mode.

        Args:
            symbol: Trading pair.
            side: "buy" or "sell".
            size: Order size.
            intended_price: Expected fill price.
            stop_loss: SL price (not placed in dry-run).
            take_profit: TP price (not placed in dry-run).

        Returns:
            Simulated fill dict.
        """
        max_slippage = self.max_slippage_pct
        slippage_factor = random.uniform(-max_slippage, max_slippage)
        fill_price = intended_price * (1 + slippage_factor)

        if fill_price <= 0:
            fill_price = intended_price

        return {
            "status": "closed",
            "filled": size,
            "avg_price": fill_price,
            "dry_run": True,
            "id": f"dry_{int(time.time() * 1000)}",
        }

    def _place_stop_loss_internal(
        self,
        symbol: str,
        side: str,
        size: float,
        sl_price: float,
    ) -> Dict[str, Any]:
        """Place stop-loss via create_order (internal, used by execute_entry)."""
        sl_side = "sell" if side == "buy" else "buy"
        try:
            return self.exchange_client.create_order(
                symbol, "stop_market", sl_side, size,
                price=sl_price,
            )
        except Exception as e:
            logger.error(f"Failed to place stop-loss: {e}")
            return {"error": str(e), "status": "error"}

    def _place_take_profit_internal(
        self,
        symbol: str,
        side: str,
        size: float,
        tp_price: float,
    ) -> Dict[str, Any]:
        """Place take-profit via create_order (internal, used by execute_entry)."""
        tp_side = "sell" if side == "buy" else "buy"
        try:
            return self.exchange_client.create_order(
                symbol, "take_profit_market", tp_side, size,
                price=tp_price,
            )
        except Exception as e:
            logger.error(f"Failed to place take-profit: {e}")
            return {"error": str(e), "status": "error"}

    def _handle_partial_fill(
        self,
        order_id: str,
        symbol: str,
        filled: float,
        size: float,
    ) -> float:
        """Poll for fill updates and cancel if fill < 50% after timeout.

        Args:
            order_id: Exchange order ID.
            symbol: Trading pair.
            filled: Current filled amount.
            size: Original order size.

        Returns:
            Updated filled amount after polling.
        """
        start_time = time.time()
        current_filled = filled

        while time.time() - start_time < self.order_timeout_sec:
            status_info = self.check_order_status(order_id, symbol)

            if status_info["status"] == "closed":
                return status_info.get("filled", current_filled)

            current_filled = status_info.get("filled", current_filled)

            if current_filled >= size:
                return current_filled

            time.sleep(0.05)

        # Timeout: check fill ratio
        if current_filled < size * 0.5:
            logger.info(
                f"Partial fill {current_filled}/{size} (<50%) after timeout, "
                f"canceling remaining"
            )
            self.cancel_order(order_id, symbol)

        return current_filled

    def check_order_status(
        self, order_id: str, symbol: str
    ) -> Dict[str, Any]:
        """Poll order status from exchange.

        Args:
            order_id: Exchange order ID.
            symbol: Trading pair.

        Returns:
            Dict with status, filled, remaining, avg_price.
        """
        try:
            order = self.exchange_client.fetch_order(order_id, symbol)
            return {
                "status": order.get("status", "unknown"),
                "filled": order.get("filled", 0) or 0,
                "remaining": order.get("remaining", 0) or 0,
                "avg_price": order.get("average") or order.get("price", 0),
            }
        except Exception as e:
            logger.error(f"Failed to check order status {order_id}: {e}")
            return {"status": "error", "error": str(e)}

    def place_stop_loss(
        self,
        symbol: str,
        side: str,
        size: float,
        sl_price: float,
    ) -> Dict[str, Any]:
        """Place a stop-loss order.

        For a long position (buy entry), the SL side is sell.
        For a short position (sell entry), the SL side is buy.

        Args:
            symbol: Trading pair.
            side: Original entry side ("buy" or "sell").
            size: Position size to protect.
            sl_price: Stop-loss trigger price.

        Returns:
            Order dict with id, or error dict on failure.
        """
        if self.dry_run:
            return {
                "id": f"dry_sl_{int(time.time() * 1000)}",
                "status": "open",
                "type": "stop_market",
                "dry_run": True,
            }

        sl_side = "sell" if side == "buy" else "buy"

        try:
            order = self.exchange_client.create_order(
                symbol,
                "stop_market",
                sl_side,
                size,
                params={"stopPrice": sl_price},
            )
            return order
        except Exception as e:
            logger.error(f"Failed to place stop-loss: {e}")
            return {"error": str(e), "status": "error"}

    def place_take_profit(
        self,
        symbol: str,
        side: str,
        size: float,
        tp_price: float,
    ) -> Dict[str, Any]:
        """Place a take-profit order.

        For a long position (buy entry), the TP side is sell.
        For a short position (sell entry), the TP side is buy.

        Args:
            symbol: Trading pair.
            side: Original entry side ("buy" or "sell").
            size: Position size to protect.
            tp_price: Take-profit trigger price.

        Returns:
            Order dict with id, or error dict on failure.
        """
        if self.dry_run:
            return {
                "id": f"dry_tp_{int(time.time() * 1000)}",
                "status": "open",
                "type": "take_profit_market",
                "dry_run": True,
            }

        tp_side = "sell" if side == "buy" else "buy"

        try:
            order = self.exchange_client.create_order(
                symbol,
                "take_profit_market",
                tp_side,
                size,
                params={"stopPrice": tp_price},
            )
            return order
        except Exception as e:
            logger.error(f"Failed to place take-profit: {e}")
            return {"error": str(e), "status": "error"}

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an open order on the exchange.

        Args:
            order_id: Exchange order ID.
            symbol: Trading pair.

        Returns:
            True on success, False on failure.
        """
        try:
            self.exchange_client.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def close_position(
        self,
        symbol: str,
        side: str,
        size: float,
    ) -> Dict[str, Any]:
        """Market close an existing position.

        For a long position (buy entry), close with a sell market order.
        For a short position (sell entry), close with a buy market order.

        Args:
            symbol: Trading pair.
            side: Original entry side ("buy" or "sell").
            size: Position size to close.

        Returns:
            Order result dict, or error dict on failure.
        """
        if self.dry_run:
            return {
                "id": f"dry_close_{int(time.time() * 1000)}",
                "status": "closed",
                "filled": size,
                "dry_run": True,
            }

        close_side = "sell" if side == "buy" else "buy"

        try:
            order = self.exchange_client.create_order(
                symbol, "market", close_side, size
            )
            return order
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return {"error": str(e), "status": "error"}
