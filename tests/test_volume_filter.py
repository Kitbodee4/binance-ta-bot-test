"""Tests for VolumeFilter strategy."""

import pytest

from newtrade.binance_ta_bot.strategy.volume_filter import VolumeFilter, calculate_volume_avg


class TestCalculateVolumeAvg:
    """Tests for calculate_volume_avg helper."""

    def test_basic_rolling_average(self):
        """Returns rolling average of volumes."""
        volumes = [100, 200, 300, 400, 500]
        result = calculate_volume_avg(volumes, period=3)
        # Window 1: [100,200,300] -> 200
        # Window 2: [200,300,400] -> 300
        # Window 3: [300,400,500] -> 400
        assert result == [200.0, 300.0, 400.0]

    def test_single_element(self):
        """Single volume with period=1 returns itself."""
        result = calculate_volume_avg([42], period=1)
        assert result == [42.0]

    def test_period_equals_length(self):
        """Period equal to list length returns single average."""
        result = calculate_volume_avg([10, 20, 30], period=3)
        assert result == [20.0]

    def test_empty_list(self):
        """Empty list returns empty list."""
        result = calculate_volume_avg([], period=5)
        assert result == []

    def test_not_enough_data(self):
        """Fewer elements than period returns empty list."""
        result = calculate_volume_avg([10, 20], period=5)
        assert result == []


class TestVolumeFilterInit:
    """Tests for VolumeFilter constructor."""

    def test_default_params(self):
        """Default constructor sets avg_period=20, spike_multiplier=1.5."""
        vf = VolumeFilter()
        assert vf.avg_period == 20
        assert vf.spike_multiplier == 1.5

    def test_custom_params(self):
        """Custom parameters are stored."""
        vf = VolumeFilter(avg_period=10, spike_multiplier=2.0)
        assert vf.avg_period == 10
        assert vf.spike_multiplier == 2.0


def _make_candle(volume: float) -> list:
    """Create a minimal OHLCV candle."""
    return [0, 0, 0, 0, 0, volume]


class TestVolumeFilterEvaluate:
    """Tests for VolumeFilter.evaluate()."""

    def test_spike_detected(self):
        """Volume > 1.5x average => is_spike True."""
        vf = VolumeFilter(avg_period=5, spike_multiplier=1.5)
        # 5 candles with volume=100, last with volume=300
        # Window [100,100,100,100,300] => avg=140, 300 > 1.5*140=210
        candles = [_make_candle(100) for _ in range(5)] + [_make_candle(300)]
        result = vf.evaluate(candles)
        assert result["is_spike"] is True
        assert result["current_volume"] == 300
        assert result["avg_volume"] == pytest.approx(140.0)

    def test_no_spike_below_threshold(self):
        """Volume <= 1.5x average => is_spike False."""
        vf = VolumeFilter(avg_period=5, spike_multiplier=1.5)
        # 5 candles with volume=100, last with volume=150 (=1.5*100)
        candles = [_make_candle(100) for _ in range(5)] + [_make_candle(150)]
        result = vf.evaluate(candles)
        assert result["is_spike"] is False

    def test_not_enough_data(self):
        """Fewer candles than avg_period => is_spike False."""
        vf = VolumeFilter(avg_period=20, spike_multiplier=1.5)
        candles = [_make_candle(100) for _ in range(10)]
        result = vf.evaluate(candles)
        assert result["is_spike"] is False
        assert result["current_volume"] == 100
        assert result["avg_volume"] == 0

    def test_exact_period_data(self):
        """Exactly avg_period candles uses all but last for average."""
        vf = VolumeFilter(avg_period=5, spike_multiplier=1.5)
        # First 4 candles vol=100, last candle vol=300
        candles = [_make_candle(100) for _ in range(4)] + [_make_candle(300)]
        result = vf.evaluate(candles)
        # avg of last 5 volumes including current: all 5 are [100,100,100,100,300]
        # avg = 140, 300 > 1.5*140=210 => True
        assert result["is_spike"] is True
        assert result["current_volume"] == 300
        assert result["avg_volume"] == pytest.approx(140.0)

    def test_spike_multiplier_custom(self):
        """Custom spike_multiplier changes threshold."""
        vf = VolumeFilter(avg_period=3, spike_multiplier=2.0)
        # Window [100,100,180] => avg=126.67, 180 < 2.0*126.67=253.33
        candles = [_make_candle(100) for _ in range(2)] + [_make_candle(180)]
        result = vf.evaluate(candles)
        assert result["is_spike"] is False

        # Window [100,100,500] => avg=233.33, 500 > 2.0*233.33=466.66
        candles2 = [_make_candle(100) for _ in range(2)] + [_make_candle(500)]
        result2 = vf.evaluate(candles2)
        assert result2["is_spike"] is True
