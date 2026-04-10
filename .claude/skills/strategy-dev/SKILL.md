---
name: strategy-dev
description: Assists with developing, testing, and refining trading strategies for the Binance TA bot. Use when creating new indicators, modifying strategy parameters, or testing strategy combinations.
---

# Strategy Development Skill

This Skill helps you efficiently develop, test, and refine trading strategies for the Binance TA Bot, reducing token usage by providing predefined workflows, file references, and testing patterns.

## When to use this Skill

Use this Skill when:
- Creating new trading strategy components (EMA, RSI, volume filters, etc.)
- Modifying existing strategy parameters or logic
- Testing strategy combinations and parameter sets
- Validating strategy logic before implementation
- Backtesting strategy signals against historical data
- Troubleshooting strategy-related issues

## Instructions

### Strategy Component References

**Core Strategy Files:**
- Main Strategy: `strategy/multi_tf_strategy.py` (combines EMA/RSI/volume)
- EMA Crossover: `strategy/ema_crossover.py` (fast/slow EMA signals)
- RSI Filter: `strategy/rsi_filter.py` (overbought/oversold conditions)
- Volume Filter: `strategy/volume_filter.py` (volume spike detection)

### Common Operations

**Testing Strategy Components:**
```bash
# Test EMA crossover logic
pytest tests/test_ema_crossover.py -v

# Test RSI filter logic  
pytest tests/test_rsi_filter.py -v

# Test volume filter logic
pytest tests/test_volume_filter.py -v

# Test combined strategy
pytest tests/test_multi_tf_strategy.py -v

# Run all strategy tests
pytest tests/test_*strategy*.py
```

**Creating New Strategy Components:**

1. **Create new file** in `strategy/` directory:
   ```bash
   # Example: creating a new MACD strategy component
   touch strategy/macd_filter.py
   ```

2. **Follow existing patterns** - reference existing components:
   ```python
   # strategy/macd_filter.py
   class MACDFilter:
       def __init__(self, fast_period=12, slow_period=26, signal_period=9):
           self.fast_period = fast_period
           self.slow_period = slow_period
           self.signal_period = signal_period
       
       def calculate(self, closes):
           # MACD calculation logic
           pass
           
       def generate_signal(self, closes):
           # Signal generation logic
           pass
   ```

3. **Add to strategy configuration** - update `config.yaml`:
   ```yaml
   # In strategy section
   macd_enabled: true
   macd_fast: 12
   macd_slow: 26
   macd_signal: 9
   ```

**Parameter Testing Workflow:**

```bash
# 1. View current strategy config
cat config.yaml | grep -A 10 "strategy:"

# 2. Modify parameters for testing
# (edit config.yaml directly or use config-manager skill)

# 3. Run tests to validate logic
pytest tests/test_ema_crossover.py tests/test_rsi_filter.py tests/test_volume_filter.py -v

# 4. Run bot in dry-run mode to observe behavior
python -m newtrade.binance_ta_bot --mode execute --dry-run --verbose

# 5. Check logs for signal generation
grep -i "signal\|entry\|exit" logs/latest.log
```

**Backtesting Strategy Signals:**

```bash
# Example backtesting workflow
python -c "
import pandas as pd
from strategy.ema_crossover import EMACrossover
from strategy.rsi_filter import RSIFilter
from strategy.volume_filter import VolumeFilter

# Load historical data (you would load your actual data)
# data = load_historical_data('BTC/USDT', '15m', 1000)

# Initialize strategies
ema = EMACrossover(fast=9, slow=21)
rsi = RSIFilter(period=14, overbought=70, oversold=30)
volume = VolumeFilter(avg_period=20, spike_mult=1.5)

# Generate signals (example)
# ema_signal = ema.generate_signal(data['close'])
# rsi_signal = rsi.generate_signal(data['close'])  
# volume_signal = volume.generate_signal(data['volume'])
"
```

### Best Practices for Strategy Development

1. **Start with existing patterns** - Copy and modify existing strategy components rather than creating from scratch
2. **Test in isolation** - Validate each strategy component individually before combining
3. **Use meaningful parameter names** - Make configuration self-documenting
4. **Keep strategies focused** - Each component should have a single, clear purpose
5. **Document assumptions** - Add comments explaining the logic behind parameters
6. **Test edge cases** - Consider what happens with extreme values or insufficient data
7. **Follow naming conventions** - Use descriptive names like `ema_crossover.py`, `rsi_filter.py`

### Common Strategy Modifications

**Adjusting EMA Parameters:**
```yaml
# In config.yaml under strategy:
ema_fast: 12   # was 9
ema_slow: 26   # was 21
```

**Modifying RSI Thresholds:**
```yaml
# In config.yaml under strategy:
rsi_overbought: 80   # was 70
rsi_oversold: 20     # was 30
```

**Changing Volume Filter Sensitivity:**
```yaml
# In config.yaml under strategy:
volume_spike_mult: 2.0   # was 1.5
volume_avg_period: 50    # was 20
```

### Troubleshooting Strategy Issues

**No signals being generated:**
- Check if enough historical data is available (look at `entry_limit`/`trend_limit` in config)
- Verify indicator calculations are producing expected values
- Check that signal thresholds are reachable with current market conditions
- Look at logs for calculation errors

**Too many/few signals:**
- Adjust indicator sensitivity (EMA periods, RSI thresholds, volume multipliers)
- Consider market conditions - some parameters work better in trending vs ranging markets
- Check timeframe appropriateness (shorter timeframes need more sensitive parameters)

**Signals conflicting with other components:**
- Verify each component works independently first
- Check how signals are combined in `multi_tf_strategy.py`
- Consider adding signal weighting or confirmation requirements

### Examples

### Example 1: Testing EMA Crossover Changes
```
# 1. Backup current config
cp config.yaml config.yaml.backup

# 2. Modify EMA parameters for testing
# Edit config.yaml: change ema_fast to 12, ema_slow to 26

# 3. Test EMA logic in isolation
pytest tests/test_ema_crossover.py -v

# 4. Run bot in dry-run to see signals
python -m newtrade.binance_ta_bot --mode execute --dry-run --verbose | grep -i ema

# 5. If results are good, keep changes; otherwise restore
# cp config.yaml.backup config.yaml
```

### Example 2: Adding New Strategy Component
```
# 1. Create new component file
touch strategy/adx_filter.py

# 2. Implement based on existing patterns
# (reference ema_crossover.py or rsi_filter.py structure)

# 3. Add configuration options to config.yaml
# Under strategy section:
#   adx_enabled: true
#   adx_period: 14
#   adx_threshold: 25

# 4. Test new component
pytest tests/test_adx_filter.py -v  # after creating test file

# 5. Integrate with main strategy
# Edit strategy/multi_tf_strategy.py to include ADX logic
```

## Advanced Usage

For repetitive strategy development tasks, consider creating command aliases:
```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc)
alias strat-test="pytest tests/test_*strategy*.py"
alias strat-ema-test="pytest tests/test_ema_crossover.py"
alias strat-rsi-test="pytest tests/test_rsi_filter.py"
alias strat-volume-test="pytest tests/test_volume_filter.py"
alias strat-run="python -m newtrade.binance_ta_bot --mode execute --dry-run --verbose"
```

See [reference.md](reference.md) for detailed strategy development guides, indicator reference sheets, and advanced testing methodologies.