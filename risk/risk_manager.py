"""Risk management: position sizing, SL/TP, limits."""

from loguru import logger
import numpy as np


class RiskManager:
    """Manages risk for trading operations."""

    def __init__(
        self,
        risk_per_trade: float = 0.01,
        max_leverage: int = 3,
        max_positions: int = 3,
        daily_loss_limit: float = 0.03,
        weekly_loss_limit: float = 0.08,
        min_sl_pct: float = 0.005,
        max_sl_pct: float = 0.03,
        gap_multiplier: float = 1.5,
        max_directional_exposure: float = 0.6,
        consecutive_loss_pause: int = 3,
        consecutive_loss_halt: int = 5,
        volatility_adjustment: bool = True,
        volatility_lookback: int = 14,
        volatility_risk_range: tuple[float, float] = (0.005, 0.02),  # min 0.5%, max 2%
        # Enhanced risk management parameters
        dynamic_position_sizing: bool = True,
        max_volatility_positions: int = 2,
        correlation_threshold: float = 0.7,
        max_correlated_exposure: float = 0.4,
        time_based_risk_reduction: bool = True,
        low_liquidity_hours: list[int] = [0, 1, 2, 3, 4, 5],  # UTC hours typically low liquidity
        liquidity_risk_factor: float = 0.5,  # Reduce risk by 50% during low liquidity
        profit_protecting_sl: bool = True,
    ):
        self.risk_per_trade = risk_per_trade
        self.max_leverage = max_leverage
        self.max_positions = max_positions
        self.daily_loss_limit = daily_loss_limit
        self.weekly_loss_limit = weekly_loss_limit
        self.min_sl_pct = min_sl_pct
        self.max_sl_pct = max_sl_pct
        self.gap_multiplier = gap_multiplier
        self.max_directional_exposure = max_directional_exposure
        self.consecutive_loss_pause = consecutive_loss_pause
        self.consecutive_loss_halt = consecutive_loss_halt
        self.volatility_adjustment = volatility_adjustment
        self.volatility_lookback = volatility_lookback
        self.volatility_risk_range = volatility_risk_range
        self._atr_cache = {}  # Cache ATR values by symbol
        self._position_timestamps = {}  # Track when positions were opened
        self._daily_volume_profile = {}  # Cache volume profiles for time-based adjustments
        # Enhanced risk management parameters
        self.dynamic_position_sizing = dynamic_position_sizing
        self.max_volatility_positions = max_volatility_positions
        self.correlation_threshold = correlation_threshold
        self.max_correlated_exposure = max_correlated_exposure
        self.time_based_risk_reduction = time_based_risk_reduction
        self.low_liquidity_hours = low_liquidity_hours  # List of hours [0-23] when to reduce risk
        self.liquidity_risk_factor = liquidity_risk_factor  # Multiplier for risk during low liquidity (e.g., 0.5 for 50% reduction)
        self.profit_protecting_sl = profit_protecting_sl  # Enable profit-protecting stop loss adjustments

    def _calculate_atr(self, high: list[float], low: list[float], close: list[float], period: int) -> float:
        """Calculate Average True Range (ATR) for given price data.

        Args:
            high: List of high prices
            low: List of low prices
            close: List of close prices
            period: ATR period

        Returns:
            ATR value
        """
        if len(high) < period + 1 or len(low) < period + 1 or len(close) < period + 1:
            return 0.0

        # Calculate True Range for each period
        tr_values = []
        for i in range(1, len(high)):
            high_low = high[i] - low[i]
            high_close_prev = abs(high[i] - close[i-1])
            low_close_prev = abs(low[i] - close[i-1])
            tr = max(high_low, high_close_prev, low_close_prev)
            tr_values.append(tr)

        # Calculate ATR using Wilder's smoothing (similar to RSI)
        if len(tr_values) < period:
            return sum(tr_values) / len(tr_values) if tr_values else 0.0

        # First ATR is simple average of first 'period' TR values
        atr = sum(tr_values[:period]) / period

        # Apply Wilder's smoothing for subsequent values
        for i in range(period, len(tr_values)):
            atr = (atr * (period - 1) + tr_values[i]) / period

        return atr

    def _get_atr_for_symbol(self, exchange_client, symbol: str, timeframe: str = "1h") -> float:
        """Get ATR value for a symbol, with caching to avoid redundant calculations.

        Args:
            exchange_client: Exchange client instance
            symbol: Trading pair symbol
            timeframe: Timeframe for ATR calculation

        Returns:
            ATR value as percentage of price
        """
        cache_key = f"{symbol}_{timeframe}"

        # Check if we have cached ATR (simple time-based cache for now)
        if cache_key in self._atr_cache:
            return self._atr_cache[cache_key]

        try:
            # Fetch OHLCV data for ATR calculation
            ohlcv = exchange_client.fetch_ohlcv(symbol, timeframe, self.volatility_lookback + 1)

            if len(ohlcv) < self.volatility_lookback + 1:
                # Not enough data, return default volatility
                atr_pct = 0.02  # 2% default
            else:
                # Extract high, low, close prices
                high = [candle[2] for candle in ohlcv]
                low = [candle[3] for candle in ohlcv]
                close = [candle[4] for candle in ohlcv]

                # Calculate ATR
                atr_value = self._calculate_atr(high, low, close, self.volatility_lookback)

                # Convert to percentage of current price
                current_price = close[-1] if close else 0
                atr_pct = (atr_value / current_price) if current_price > 0 else 0.02

            # Cache the result
            self._atr_cache[cache_key] = atr_pct
            return atr_pct

        except Exception as e:
            # If we can't fetch data, return a reasonable default
            logger.warning(f"Could not calculate ATR for {symbol}: {e}. Using default volatility.")
            return 0.02  # 2% default

    def _adjust_risk_for_volatility(self, base_risk: float, current_atr_pct: float) -> float:
        """Adjust risk percentage based on current volatility.

        Args:
            base_risk: Base risk percentage (e.g., 0.01 for 1%)
            current_atr_pct: Current ATR as percentage of price

        Returns:
            Adjusted risk percentage
        """
        if not self.volatility_adjustment:
            return base_risk

        # Define volatility ranges for normalization
        # These are example values - in practice, these should be tuned based on historical data
        min_volatility = 0.01   # 1% ATR
        max_volatility = 0.05   # 5% ATR

        # Clamp ATR to our expected range
        clamped_atr = max(min_volatility, min(max_volatility, current_atr_pct))

        # Normalize to 0-1 range (0 = low volatility, 1 = high volatility)
        if max_volatility > min_volatility:
            volatility_normalized = (clamped_atr - min_volatility) / (max_volatility - min_volatility)
        else:
            volatility_normalized = 0.5

        # Invert the relationship: high volatility = lower risk, low volatility = higher risk
        # Map to our risk range: [min_risk, max_risk]
        min_risk, max_risk = self.volatility_risk_range
        adjusted_risk = max_risk - (volatility_normalized * (max_risk - min_risk))

        # Ensure we don't exceed the base risk as an upper limit in normal conditions
        # This prevents increasing risk beyond what the user intentionally set
        return min(base_risk, adjusted_risk)

    def calculate_position_size(
        self,
        equity: float,
        entry_price: float,
        stop_loss: float,
        exchange_client=None,
        symbol: str = "",
    ) -> float:
        """Calculate position size in contracts.

        Formula:
            position_size_usd = (equity * risk_pct) / sl_distance_pct
            contracts = position_size_usd / entry_price

        Capped to max_leverage * equity / entry_price.
        """
        if equity <= 0 or entry_price <= 0:
            return 0.0

        sl_distance_pct = abs(entry_price - stop_loss) / entry_price
        if sl_distance_pct == 0:
            return 0.0

        # Calculate base risk amount
        risk_amount = equity * self.risk_per_trade

        # Adjust risk for volatility if exchange client and symbol are provided
        if exchange_client and symbol:
            atr_pct = self._get_atr_for_symbol(exchange_client, symbol)
            adjusted_risk_pct = self._adjust_risk_for_volatility(self.risk_per_trade, atr_pct)
            risk_amount = equity * adjusted_risk_pct

            logger.debug(f"Volatility-adjusted risk for {symbol}: {self.risk_per_trade:.3f} -> {adjusted_risk_pct:.3f} (ATR: {atr_pct:.3f})")
        else:
            adjusted_risk_pct = self.risk_per_trade

        size_usd = risk_amount / sl_distance_pct
        contracts = size_usd / entry_price

        # Cap by max leverage
        max_notional = equity * self.max_leverage
        max_contracts = max_notional / entry_price
        if contracts > max_contracts:
            logger.debug(
                f"Size capped by leverage: {contracts:.4f} -> "
                f"{max_contracts:.4f}"
            )
            contracts = max_contracts

        # Apply time-based risk reduction if enabled
        if self.time_based_risk_reduction and self._is_low_liquidity_time():
            original_contracts = contracts
            contracts *= self.liquidity_risk_factor
            logger.debug(
                f"Size reduced for low liquidity: {original_contracts:.4f} -> "
                f"{contracts:.4f} (factor: {self.liquidity_risk_factor})"
            )

        return contracts
        self.volatility_adjustment = volatility_adjustment
        self.volatility_lookback = volatility_lookback
        self.volatility_risk_range = volatility_risk_range
        self._atr_cache = {}  # Cache ATR values by symbol

    def calculate_position_size(
        self,
        equity: float,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """Calculate position size in contracts.

        Formula:
            position_size_usd = (equity * risk_pct) / sl_distance_pct
            contracts = position_size_usd / entry_price

        Capped to max_leverage * equity / entry_price.
        """
        if equity <= 0 or entry_price <= 0:
            return 0.0

        sl_distance_pct = abs(entry_price - stop_loss) / entry_price
        if sl_distance_pct == 0:
            return 0.0

        risk_amount = equity * self.risk_per_trade
        size_usd = risk_amount / sl_distance_pct
        contracts = size_usd / entry_price

        # Cap by max leverage
        max_notional = equity * self.max_leverage
        max_contracts = max_notional / entry_price
        if contracts > max_contracts:
            logger.debug(
                f"Size capped by leverage: {contracts:.4f} -> "
                f"{max_contracts:.4f}"
            )
            contracts = max_contracts

        # Apply time-based risk reduction if enabled
        if self.time_based_risk_reduction and self._is_low_liquidity_time():
            original_contracts = contracts
            contracts *= self.liquidity_risk_factor
            logger.debug(
                f"Size reduced for low liquidity: {original_contracts:.4f} -> "
                f"{contracts:.4f} (factor: {self.liquidity_risk_factor})"
            )

        return contracts

    def check_position_limit(
        self,
        open_positions: list,
    ) -> bool:
        """Check if we can open another position.

        Returns True if under the limit, False otherwise.
        """
        return len(open_positions) < self.max_positions

    def check_daily_loss_limit(
        self,
        daily_pnl: float,
        equity: float,
    ) -> bool:
        """Check daily loss limit.

        Returns True if within limit (can trade).
        """
        if daily_pnl >= 0:
            return True
        loss_pct = abs(daily_pnl) / equity
        return loss_pct < self.daily_loss_limit

    def check_weekly_loss_limit(
        self,
        weekly_pnl: float,
        equity: float,
    ) -> bool:
        """Check weekly loss limit.

        Returns True if within limit (can trade).
        """
        if weekly_pnl >= 0:
            return True
        loss_pct = abs(weekly_pnl) / equity
        return loss_pct < self.weekly_loss_limit

    def check_directional_exposure(
        self,
        positions: list,
        equity: float,
    ) -> bool:
        """Check max net directional exposure.

        Net exposure = |long_notional - short_notional|.
        Must be <= max_directional_exposure * equity.
        """
        if not positions or equity <= 0:
            return True

        long_notional = sum(
            p.get("size", 0) * p.get("entry_price", 0)
            for p in positions if p.get("side") == "long"
        )
        short_notional = sum(
            p.get("size", 0) * p.get("entry_price", 0)
            for p in positions if p.get("side") == "short"
        )
        net_exposure = abs(long_notional - short_notional)
        max_exposure = equity * self.max_directional_exposure
        return net_exposure <= max_exposure

    def calculate_sl_tp(
        self,
        entry_price: float,
        side: str,
        swing_low: float,
        swing_high: float,
    ) -> dict:
        """Calculate stop-loss and take-profit levels.

        Long: SL at/below swing_low, TP = Entry + 2 * (Entry - SL).
        Short: SL at/above swing_high, TP = Entry - 2 * (SL - Entry).

        Enforces min/max SL distance bounds.
        """
        if side not in ("long", "short"):
            raise ValueError(
                f"side must be 'long' or 'short', got '{side}'"
            )

        if side == "long":
            sl_distance = entry_price - swing_low
            # Enforce min/max SL distance
            min_dist = entry_price * self.min_sl_pct
            max_dist = entry_price * self.max_sl_pct
            sl_distance = max(min_dist, min(sl_distance, max_dist))

            stop_loss = entry_price - sl_distance
            take_profit = entry_price + 2 * sl_distance
        else:
            sl_distance = swing_high - entry_price
            min_dist = entry_price * self.min_sl_pct
            max_dist = entry_price * self.max_sl_pct
            sl_distance = max(min_dist, min(sl_distance, max_dist))

            stop_loss = entry_price + sl_distance
            take_profit = entry_price - 2 * sl_distance

        return {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

    def check_consecutive_loss(
        self,
        consecutive_losses: int,
    ) -> dict:
        """Check consecutive loss protection.

        0-2 losses: trade normally.
        3-4 losses: pause for 4 hours.
        5+ losses: halt for the day.
        """
        if consecutive_losses >= self.consecutive_loss_halt:
            return {
                "action": "halt",
                "reason": (
                    f"Halt: {consecutive_losses} consecutive losses "
                    f"exceeds limit of {self.consecutive_loss_halt}"
                ),
            }

        if consecutive_losses >= self.consecutive_loss_pause:
            return {
                "action": "pause",
                "duration_hours": 4,
                "reason": (
                    f"Pause: {consecutive_losses} consecutive losses, "
                    f"waiting 4 hours"
                ),
            }

        return {"action": "trade"}

    def _get_current_utc_hour(self) -> int:
        """Get current UTC hour for time-based adjustments.

        Returns:
            Current hour in UTC (0-23)
        """
        import datetime
        return datetime.datetime.utcnow().hour

    def _is_low_liquidity_time(self) -> bool:
        """Check if current time is in low liquidity hours.

        Returns:
            True if current time is in low liquidity period
        """
        if not self.time_based_risk_reduction:
            return False

        current_hour = self._get_current_utc_hour()
        return current_hour in self.low_liquidity_hours

    def _calculate_dynamic_max_positions(self, base_max_positions: int, current_volatility_pct: float) -> int:
        """Calculate dynamic maximum positions based on volatility.

        Args:
            base_max_positions: Base maximum positions allowed
            current_volatility_pct: Current volatility as percentage (ATR/price)

        Returns:
            Adjusted maximum positions
        """
        if not self.dynamic_position_sizing:
            return base_max_positions

        # Define volatility thresholds
        low_volatility = 0.01   # 1%
        high_volatility = 0.04  # 4%

        # Clamp volatility to range
        clamped_vol = max(low_volatility, min(high_volatility, current_volatility_pct))

        # Invert relationship: high volatility = fewer positions
        if high_volatility > low_volatility:
            volatility_factor = (high_volatility - clamped_vol) / (high_volatility - low_volatility)
        else:
            volatility_factor = 0.5

        # Calculate adjusted max positions (minimum 1)
        adjusted_max = max(1, int(base_max_positions * (0.5 + 0.5 * volatility_factor)))
        return min(adjusted_max, base_max_positions)  # Never exceed base maximum

    def _get_position_age_hours(self, symbol: str) -> float:
        """Get how long a position has been open in hours.

        Args:
            symbol: Position symbol

        Returns:
            Position age in hours, or 0 if not tracked
        """
        if symbol not in self._position_timestamps:
            return 0.0

        import datetime, time
        elapsed_seconds = time.time() - self._position_timestamps[symbol]
        return elapsed_seconds / 3600

    def _update_position_timestamp(self, symbol: str, is_opening: bool):
        """Update timestamp for position tracking.

        Args:
            symbol: Position symbol
            is_opening: True if opening position, False if closing
        """
        import time
        if is_opening:
            self._position_timestamps[symbol] = time.time()
        else:
            # Remove timestamp when position closes
            self._position_timestamps.pop(symbol, None)

    def _calculate_correlation_adjustment(self, symbol: str, positions: list, exchange_client) -> float:
        """Calculate risk adjustment based on correlation with existing positions.

        This is a simplified implementation. In practice, you'd want to calculate
        actual correlations using historical price data.

        Args:
            symbol: Symbol to check
            positions: List of current positions
            exchange_client: Exchange client for fetching data

        Returns:
            Risk multiplier (1.0 = no adjustment, < 1.0 = reduce risk)
        """
        # Simplified approach: check if we already have positions in highly correlated assets
        # For crypto, we can use basic grouping (BTC, ETH, etc.)

        # Define correlation groups (simplified)
        btc_group = ['BTC/USDT', 'BTC/USDC']
        eth_group = ['ETH/USDT', 'ETH/USDC']
        major_group = ['BNB/USDT', 'ADA/USDT', 'SOL/USDT', 'XRP/USDT', 'DOT/USDT', 'DOGE/USDT']

        def get_group(sym):
            sym_base = sym.split('/')[0]  # Get base currency
            if sym_base in ['BTC']:
                return 'btc'
            elif sym_base in ['ETH']:
                return 'eth'
            elif sym_base in ['BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'DOGE']:
                return 'major'
            else:
                return 'other'

        target_group = get_group(symbol)

        # Count existing positions in same group
        same_group_count = sum(1 for p in positions if get_group(p.get('symbol', '')) == target_group)

        # If we already have positions in this group, reduce risk for additional positions
        if same_group_count > 0:
            # Reduction factor: more positions = less additional risk allowed
            reduction = min(0.5, same_group_count * 0.2)  # Up to 50% reduction
            return 1.0 - reduction

        return 1.0  # No adjustment if no similar positions

    def check_all_limits(
        self,
        equity: float,
        daily_pnl: float,
        weekly_pnl: float,
        open_positions: list,
        consecutive_losses: int,
        exchange_client=None,
        symbol: str = "",
    ) -> dict:
        """Check all risk limits.

        Returns {"approved": bool, "reason": str}.
        """
        # Position limit
        if not self.check_position_limit(open_positions):
            return {
                "approved": False,
                "reason": (
                    f"Position limit reached: {len(open_positions)}/"
                    f"{self.max_positions}"
                ),
            }

        # Daily loss limit
        if not self.check_daily_loss_limit(daily_pnl, equity):
            return {
                "approved": False,
                "reason": (
                    f"Daily loss limit hit: "
                    f"{abs(daily_pnl) / equity:.1%} >= "
                    f"{self.daily_loss_limit:.1%}"
                ),
            }

        # Weekly loss limit
        if not self.check_weekly_loss_limit(weekly_pnl, equity):
            return {
                "approved": False,
                "reason": (
                    f"Weekly loss limit hit: "
                    f"{abs(weekly_pnl) / equity:.1%} >= "
                    f"{self.weekly_loss_limit:.1%}"
                ),
            }

        # Consecutive loss protection
        loss_check = self.check_consecutive_loss(consecutive_losses)
        if loss_check["action"] != "trade":
            return {
                "approved": False,
                "reason": loss_check.get("reason", "Consecutive loss limit"),
            }

        # Directional exposure
        if not self.check_directional_exposure(open_positions, equity):
            return {
                "approved": False,
                "reason": "Directional exposure limit exceeded",
            }

        # Enhanced risk management checks
        # Dynamic position sizing based on volatility
        if self.dynamic_position_sizing and open_positions:
            # Calculate average volatility across open positions for adjustment
            # For simplicity, we'll use a placeholder volatility value
            # In practice, you'd calculate average ATR across positions
            current_volatility_pct = 0.02  # Placeholder - would be calculated from actual data
            dynamic_max_positions = self._calculate_dynamic_max_positions(
                self.max_positions, current_volatility_pct
            )
            if len(open_positions) >= dynamic_max_positions:
                return {
                    "approved": False,
                    "reason": (
                        f"Dynamic position limit reached: {len(open_positions)}/"
                        f"{dynamic_max_positions} (volatility-adjusted)"
                    ),
                }

        # Correlation-adjusted exposure check
        if exchange_client and symbol and open_positions:
            correlation_adjustment = self._calculate_correlation_adjustment(symbol, open_positions, exchange_client)
            if correlation_adjustment < 0.5:  # Significant correlation reduction
                return {
                    "approved": False,
                    "reason": (
                        f"High correlation with existing positions. "
                        f"Risk adjustment factor: {correlation_adjustment:.2f}"
                    ),
                }

        # Time-based risk reduction
        if self._is_low_liquidity_time():
            # During low liquidity, we could reduce position sizes or increase caution
            # For now, we'll just log this condition - actual implementation
            # would modify position sizing in calculate_position_size
            logger.info("Trading during low liquidity hours - consider reducing position sizes")

        return {"approved": True, "reason": "All limits OK"}
