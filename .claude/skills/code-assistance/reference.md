# Code Assistance Reference

## Project Structure Overview

```
binance_ta_bot/
├── __main__.py              # Entry point
├── main.py                  # CLI and bot lifecycle
├── config.yaml              # Main configuration
├── core/                    # Core components
│   ├── bot_engine.py        # Main orchestration
│   ├── exchange_client.py   # CCXT/Binance wrapper
│   └── state_manager.py     # JSON persistence
├── scanner/                 # Pair scanning
│   └── pair_scanner.py      # Volume-based selection
├── strategy/                # Trading strategies
│   ├── multi_tf_strategy.py # Multi-timeframe EMA/RSI/volume
│   ├── ema_crossover.py     # EMA crossover logic
│   ├── rsi_filter.py        # RSI filtering
│   └── volume_filter.py     # Volume filtering
├── risk/                    # Risk management
│   ├── risk_manager.py      # Position sizing, limits
│   ├── circuit_breaker.py   # Flash crash detection
│   └── liquidation_guard.py # Liquidation monitoring
├── execution/               # Order execution
│   └── order_executor.py    # Slippage-protected execution
├── utils/                   # Utility functions
│   ├── helpers.py           # Config loading, etc.
│   ├── logger.py            # Logging setup
│   └── trade_log.py         # Trade logging
└── tests/                   # Test suite
    ├── unit tests for each module
    └── integration/         # Integration tests
```

## Key Conventions

### Naming Patterns
- Modules: snake_case (e.g., `pair_scanner.py`)
- Classes: PascalCase (e.g., `BotEngine`)
- Functions/variables: snake_case
- Constants: UPPER_SNAKE_CASE
- Configuration keys: snake_case

### File Organization
- Each major component gets its own directory under the appropriate category
- Strategy components are individual filters that get composed
- Risk components are separate concerns that wrap the execution flow
- Utilities are shared helpers used across modules

### Data Flow Patterns
1. **Initialization**: main.py → BotEngine → all components instantiated
2. **Main Loop**: BotEngine coordinates:
   - PairScanner → selects trading pairs
   - MultiTimeframeStrategy → generates signals
   - RiskManager → validates and sizes positions
   - OrderExecutor → places orders with slippage protection
   - CircuitBreaker/LiquidationGuard → monitor for emergency conditions
3. **State Management**: StateManager persists/restores bot state between runs

### Configuration Structure (config.yaml)
```yaml
exchange:
  name: binanceusdm
  # API keys from environment variables

scanner:
  top_n_pairs: 20
  min_volume_usd: 10000000
  exclude_patterns: []

strategy:
  entry_tf: 1m
  trend_tf: 15m
  ema_fast: 9
  ema_slow: 21
  rsi_period: 14
  rsi_overbought: 70
  rsi_oversold: 30
  volume_avg_period: 20
  volume_spike_mult: 1.5
  htf_ema_fast: 50
  htf_ema_slow: 200
  htf_ranging_threshold_pct: 0.005

risk:
  risk_per_trade: 0.01
  max_leverage: 3
  max_positions: 3
  daily_loss_limit: 0.03
  weekly_loss_limit: 0.08
  min_sl_pct: 0.005
  max_sl_pct: 0.03
  gap_multiplier: 1.5
  max_directional_exposure: 0.6
  consecutive_loss_pause: 3
  consecutive_loss_halt: 5

circuit_breaker:
  flash_crash_pct: 0.05
  halt_duration_min: 60
  max_slippage_pct: 0.001

bot:
  scan_interval_sec: 60
  dry_run: true
  log_level: INFO
  initial_equity: 1000
```

## Extension Points

### Adding New Strategy Components
1. Create new filter in `strategy/` (e.g., `macd_filter.py`)
2. Follow existing pattern: class with `__init__` and `filter` method
3. Import and compose in `multi_tf_strategy.py`
4. Add configuration to `config.yaml` under strategy section
5. Add tests in `tests/test_<component>.py`

### Adding New Risk Controls
1. Create new module in `risk/` directory
2. Integrate into BotEngine initialization in `main.py`
3. Hook into appropriate place in execution flow
4. Add configuration parameters
5. Add tests

### Modifying Existing Components
- Follow existing code style and patterns
- Maintain backward compatibility where possible
- Update corresponding tests
- Document any configuration changes

## Common Debugging Patterns

### Logging
- Use `logger.debug()` for detailed tracing
- Use `logger.info()` for general information
- Use `logger.warning()` for recoverable issues
- Use `logger.error()` for critical problems
- Enable with `--verbose` flag or `log_level: DEBUG` in config

### State Inspection
- Check `state_ta_bot.json` for current bot state
- Use `--mode status` to see current state
- Monitor logs for component interactions

### Testing
- Run `pytest` for full test suite
- Use `pytest -v` for verbose output
- Use `pytest tests/test_specific.py` for targeted testing
- Check `tests/conftest.py` for shared fixtures

## SDLC Guidelines for This Project

### Planning Phase
1. Understand existing patterns and conventions
2. Identify where new functionality fits
3. Determine required configuration changes
4. Plan test coverage

### Implementation Phase
1. Follow existing code style (PEP 8 with project specifics)
2. Add logging for observability
3. Handle edge cases and error conditions
4. Write unit tests alongside implementation

### Testing Phase
1. Run existing tests to ensure no regressions
2. Add new tests for new functionality
3. Test edge cases and error conditions
4. Verify integration with existing components

### Deployment Phase
1. Verify configuration is valid
2. Check API keys and permissions
3. Start in dry-run mode first
4. Monitor logs and state transitions
5. Gradually increase exposure/risk limits

## Troubleshooting Common Issues

### Configuration Problems
- Invalid YAML syntax: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
- Missing required sections
- Invalid timeframe values (must be Binance-supported)
- Numeric values outside expected ranges

### Connection Issues
- API key/secret not set or invalid
- Network connectivity problems
- Binance API rate limits or downtime
- Incorrect exchange name in config

### Logic Errors
- Signal generation not working as expected
- Position sizing calculations incorrect
- Risk limits triggering unexpectedly
- Order execution failing silently

### State Persistence Issues
- State file permissions
- Corrupted state JSON
- Missing state fields after code changes
- Version mismatches in state data