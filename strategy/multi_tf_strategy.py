"""Multi-timeframe strategy combining higher timeframe trend with momentum and entry signals."""

from loguru import logger

from .ema_crossover import (
    EmaCrossover,
    calculate_ema,
)
from .rsi_filter import RsiFilter
from .volume_filter import (
    VolumeFilter,
)
from ..utils.volatility import (
    calculate_atr_percentage,
    get_volatility_regime,
    get_dynamic_timeframes,
)
from ..utils.regime import (
    calculate_adx,
    get_market_regime,
    get_regime_adjusted_parameters
)


def detect_trend(
    candles_1h: list,
    fast_period: int = 50,
    slow_period: int = 200,
    ranging_threshold_pct: float = 0.005,
) -> str:
    if not candles_1h or len(candles_1h) < slow_period:
        return "unknown"

    closes = [c[4] for c in candles_1h]
    fast_ema_list = calculate_ema(closes, fast_period)
    slow_ema_list = calculate_ema(closes, slow_period)

    if not fast_ema_list or not slow_ema_list:
        return "unknown"

    fast_ema = fast_ema_list[-1]
    slow_ema = slow_ema_list[-1]

    if slow_ema == 0:
        return "unknown"

    if fast_ema > slow_ema:
        return "bullish"

    return "bearish"


def detect_crossover(candles: list, fast: int = 9, slow: int = 21) -> str:
    """Detect EMA state.

    Returns:
        'long' if fast > slow.
        'short' if fast < slow.
        'none' otherwise.
    """
    if not candles or len(candles) < slow + 2:
        return "none"

    closes = [c[4] for c in candles]
    fast_ema_list = calculate_ema(closes, fast)
    slow_ema_list = calculate_ema(closes, slow)

    if len(fast_ema_list) < 2 or len(slow_ema_list) < 2:
        return "none"

    curr_fast = fast_ema_list[-1]
    curr_slow = slow_ema_list[-1]

    if curr_fast > curr_slow:
        return "long"

    if curr_fast < curr_slow:
        return "short"

    return "none"


class MultiTimeframeStrategy:
    def __init__(
        self,
        ema_fast: int = 9,
        ema_slow: int = 21,
        entry_tf: str = "15m",
        trend_tf: str = "1h",
        htf_tf: str = "4h",
        entry_limit: int = 1000,
        trend_limit: int = 1000,
        htf_limit: int = 1000,
        rsi_period: int = 14,
        rsi_overbought: int = 70,
        rsi_oversold: int = 30,
        volume_avg_period: int = 20,
        volume_spike_mult: float = 1.5,
        # Higher timeframe EMA parameters
        htf_ema_fast: int = 50,
        htf_ema_slow: int = 200,
        htf_ranging_threshold_pct: float = 0.005,
        # Regime detection parameters
        regime_detection: bool = False,
        adx_period: int = 14,
        adx_threshold: int = 25,
        # Dynamic timeframe adjustment
        dynamic_timeframes: bool = False,
        volatility_lookback: int = 14,
    ):
        self.ema = EmaCrossover(ema_fast, ema_slow)
        self.rsi = RsiFilter(rsi_period, rsi_overbought, rsi_oversold)
        self.volume = VolumeFilter(volume_avg_period, volume_spike_mult)
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.htf_ema_fast = htf_ema_fast
        self.htf_ema_slow = htf_ema_slow
        self.htf_ranging_threshold_pct = htf_ranging_threshold_pct
        self.base_entry_tf = entry_tf
        self.base_trend_tf = trend_tf
        self.base_htf_tf = htf_tf
        self.entry_tf = entry_tf
        self.trend_tf = trend_tf
        self.htf_tf = htf_tf
        self.entry_limit = entry_limit
        self.trend_limit = trend_limit
        self.htf_limit = htf_limit
        self.regime_detection = regime_detection
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.dynamic_timeframes = dynamic_timeframes
        self.volatility_lookback = volatility_lookback

    def evaluate(
        self, candles_15m: list, candles_1h: list, candles_4h: list, pair: str = ""
    ) -> dict:
        default = {
            "signal": "none",
            "trend": "unknown",
            "htf_trend": "unknown",
            "ema_signal": "none",
            "rsi_ok": False,
            "volume_ok": False,
        }

        if not candles_15m or not candles_1h or not candles_4h:
            return default

        # Step 0: Regime detection if enabled
        current_regime = 'ranging'  # default
        if self.regime_detection and len(candles_1h) >= self.adx_period * 2:
            # Extract high, low, close prices from 1h candles for ADX calculation
            high_prices = [c[2] for c in candles_1h]
            low_prices = [c[3] for c in candles_1h]
            close_prices = [c[4] for c in candles_1h]

            # Calculate ADX
            adx_value = calculate_adx(high_prices, low_prices, close_prices, self.adx_period)
            current_regime = get_market_regime(adx_value, self.adx_threshold)

            logger.debug(f"{pair} ADX: {adx_value:.1f}, Regime: {current_regime}")

        # Step 0a: Adjust timeframes based on volatility if enabled
        if self.dynamic_timeframes and len(candles_1h) >= self.volatility_lookback + 1:
            # Extract high, low, close prices from 1h candles for ATR calculation
            high_prices = [c[2] for c in candles_1h]
            low_prices = [c[3] for c in candles_1h]
            close_prices = [c[4] for c in candles_1h]

            # Calculate ATR percentage
            atr_pct = calculate_atr_percentage(high_prices, low_prices, close_prices, self.volatility_lookback)

            # Get volatility regime
            volatility_regime = get_volatility_regime(atr_pct)

            # Get dynamic timeframes
            dynamic_entry_tf, dynamic_trend_tf, dynamic_htf_tf = get_dynamic_timeframes(
                self.base_entry_tf, self.base_trend_tf, self.base_htf_tf, volatility_regime
            )

            # Update timeframes for this evaluation (but don't change the object's base timeframes)
            # Note: In a real implementation, you'd want to fetch new candles with these timeframes
            # For now, we'll just log the adjustment and continue with existing candles
            logger.debug(f"{pair} Volatility regime: {volatility_regime} (ATR: {atr_pct:.3f}), "
                         f"suggested timeframes: entry={dynamic_entry_tf}, trend={dynamic_trend_tf}, htf={dynamic_htf_tf}")

        # Step 1: Detect 4h trend (higher timeframe)
        htf_trend = detect_trend(
            candles_4h,
            self.htf_ema_fast,
            self.htf_ema_slow,
            self.htf_ranging_threshold_pct,
        )

        # Step 2: Detect 1h trend
        trend = detect_trend(
            candles_1h,
            self.htf_ema_fast,
            self.htf_ema_slow,
            self.htf_ranging_threshold_pct,
        )

        # Step 3: EMA state (on 15m candles)
        ema_signal = detect_crossover(
            candles_15m, self.ema_fast, self.ema_slow
        )

        ema_result = self.ema.evaluate(candles_15m)
        fast_ema = ema_result["fast_ema"]
        slow_ema = ema_result["slow_ema"]

        logger.info(
            f"{pair} {self.entry_tf} EMA: fast={fast_ema:.4f} "
            f"slow={slow_ema:.4f} "
            f"diff={fast_ema - slow_ema:.4f} "
            f"signal={ema_signal}"
        )

        # Step 3: RSI filter
        rsi_result = self.rsi.evaluate(candles_15m)
        rsi_val = rsi_result.get("rsi", 50)
        rsi_action = rsi_result["action"]
        logger.info(
            f"{pair} RSI: rsi={rsi_val:.1f} action={rsi_action}"
        )

        # Step 4: Volume filter
        vol_result = self.volume.evaluate(candles_15m)
        volume_ok = vol_result["is_spike"]
        logger.info(
            f"{pair} Volume: "
            f"current={vol_result.get('current_volume', 0):.0f} "
            f"avg={vol_result.get('avg_volume', 0):.0f} "
            f"spike={volume_ok}"
        )

        # Apply regime-based adjustments to strategy parameters if enabled
        if self.regime_detection:
            # Prepare base parameters for adjustment
            base_params = {
                'rsi_overbought': self.rsi.overbought,
                'rsi_oversold': self.rsi.oversold,
                'volume_spike_mult': self.volume.spike_multiplier,
                'ema_fast': self.ema_fast,
                'ema_slow': self.ema_slow,
                'htf_ema_fast': self.htf_ema_fast,
                'htf_ema_slow': self.htf_ema_slow
            }

            # Get regime-adjusted parameters
            adjusted_params = get_regime_adjusted_parameters(base_params, current_regime)

            # Extract adjusted values for use in filters
            adjusted_rsi_overbought = adjusted_params['rsi_overbought']
            adjusted_rsi_oversold = adjusted_params['rsi_oversold']
            adjusted_volume_spike_mult = adjusted_params['volume_spike_mult']
            # Note: EMA adjustments would require recreating objects - handled by dynamic timeframes or separate logic

            logger.debug(f"{pair} Regime {current_regime}: RSI[{adjusted_rsi_oversold}-{adjusted_rsi_overbought}], "
                         f"VolMult[{adjusted_volume_spike_mult}]")

        # Step 5: RSI tight filter (using regime-adjusted thresholds if enabled)
        rsi_ok = False
        if ema_signal == "long":
            rsi_low = adjusted_rsi_oversold if self.regime_detection and 'adjusted_rsi_oversold' in locals() else self.rsi.oversold
            rsi_high = adjusted_rsi_overbought if self.regime_detection and 'adjusted_rsi_overbought' in locals() else self.rsi.overbought
            # For long signals, we want RSI not too high (bullish but not overbought)
            rsi_ok = rsi_low <= rsi_val <= min(55, rsi_high)  # Cap at 55 for original logic, but respect regime ceiling
        elif ema_signal == "short":
            rsi_low = adjusted_rsi_oversold if self.regime_detection and 'adjusted_rsi_oversold' in locals() else self.rsi.oversold
            rsi_high = adjusted_rsi_overbought if self.regime_detection and 'adjusted_rsi_overbought' in locals() else self.rsi.overbought
            # For short signals, we want RSI not too low (bearish but not oversold)
            rsi_ok = max(45, rsi_low) <= rsi_val <= rsi_high  # Floor at 45 for original logic, but respect regime floor

        # Step 6: Volume filter (using regime-adjusted multiplier if enabled)
        if self.regime_detection and 'adjusted_volume_spike_mult' in locals():
            # Create a temporary volume filter with adjusted multiplier for this check
            temp_volume = VolumeFilter(self.volume.avg_period, adjusted_volume_spike_mult)
            vol_result = temp_volume.evaluate(candles_15m)
            volume_ok = vol_result["is_spike"]
            logger.info(
                f"{pair} Volume (regime-adjusted): "
                f"current={vol_result.get('current_volume', 0):.0f} "
                f"avg={vol_result.get('avg_volume', 0):.0f} "
                f"spike={volume_ok}"
            )

        # --- Alignment logic ---

        if trend == "unknown":
            logger.info(f"MTF: trend={trend} → no signal")
            return default

        if trend == "bullish" and ema_signal != "long":
            logger.info(
                f"MTF: bullish but EMA={ema_signal} → blocked"
            )
            return default

        if trend == "bearish" and ema_signal != "short":
            logger.info(
                f"MTF: bearish but EMA={ema_signal} → blocked"
            )
            return default

        if ema_signal == "none":
            logger.info("MTF: no signal → blocked")
            return default

        if not volume_ok:
            logger.info("MTF: no volume spike → blocked")
            return {
                "signal": "none",
                "trend": trend,
                "ema_signal": ema_signal,
                "rsi_ok": rsi_ok,
                "volume_ok": False,
            }

        if not rsi_ok:
            logger.info(
                f"MTF: RSI={rsi_val:.1f} outside range "
                f"for {ema_signal} → blocked"
            )
            return {
                "signal": "none",
                "trend": trend,
                "ema_signal": ema_signal,
                "rsi_ok": False,
                "volume_ok": True,
            }

        logger.info(
            f"MTF: {ema_signal} signal confirmed "
            f"(trend={trend}, rsi={rsi_val:.1f})"
        )
        return {
            "signal": ema_signal,
            "trend": trend,
            "ema_signal": ema_signal,
            "rsi_ok": True,
            "volume_ok": True,
        }
