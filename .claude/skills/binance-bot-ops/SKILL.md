---
name: binance-bot-ops
description: Provides quick access to common Binance TA bot operations like running the bot, checking status, running tests, and managing configuration. Use when you need to execute bot commands, test functionality, or manage bot settings efficiently.
---

# Binance Bot Operations Skill

This Skill provides efficient access to common operations for the Binance TA Bot, reducing token usage by providing predefined command patterns and quick references.

## When to use this Skill

Use this Skill when:
- You need to run the Binance TA bot in different modes (dry-run, live, status)
- You want to run tests (unit, integration, specific test files)
- You need to check or modify bot configuration
- You want to understand bot architecture or key files quickly
- You're troubleshooting bot behavior or performance

## Instructions

### Quick Commands Reference

**Running the Bot:**
- Dry-run (default): `python -m newtrade.binance_ta_bot`
- Live mode: `python -m newtrade.binance_ta_bot --mode execute`
- Show state: `python -m newtrade.binance_ta_bot --mode status`
- Custom config: `python -m newtrade.binance_ta_bot --config path/to/config.yaml`
- Debug logging: `python -m newtrade.binance_ta_bot --verbose`

**Testing:**
- All tests: `pytest`
- Specific test: `pytest tests/test_<module>.py`
- Integration tests: `pytest tests/integration/`
- Test with verbose output: `pytest -v tests/test_<module>.py`

**Configuration:**
- View current config: `cat config.yaml`
- Edit config: Use your preferred editor on `config.yaml`
- Reset to example: `cp config.yaml.example config.yaml` (if exists)

**Environment Setup:**
- Check API keys: `echo $BINANCE_API_KEY && echo $BINANCE_SECRET`
- Set API keys: `export BINANCE_API_KEY=your_key && export BINANCE_SECRET=your_secret`
- Load from .env: `source .env` (after copying from .env.example)

### Key File References

**Core Components:**
- Bot Engine: `core/bot_engine.py` (main orchestration loop)
- Exchange Client: `core/exchange_client.py` (CCXT wrapper)
- State Manager: `core/state_manager.py` (JSON persistence)

**Trading Flow:**
- Pair Scanner: `scanner/pair_scanner.py` (volume-based pair selection)
- Strategy: `strategy/multi_tf_strategy.py` (EMA/RSI/volume across timeframes)
- Risk Manager: `risk/risk_manager.py` (position sizing, leverage, loss limits)
- Circuit Breaker: `risk/circuit_breaker.py` (flash crash detection/halt)
- Liquidation Guard: `risk/liquidation_guard.py` (liquidation monitoring/auto-close)
- Order Executor: `execution/order_executor.py` (slippage-protected execution)

**Configuration & Utilities:**
- Main Config: `config.yaml` (all sections: exchange, strategy, risk, etc.)
- Entry Point: `__main__.py` → `main.py:main()`
- Strategy Components: `strategy/ema_crossover.py`, `strategy/rsi_filter.py`, `strategy/volume_filter.py`
- Utilities: `utils/helpers.py` (config loading), `utils/logger.py`, `utils/trade_log.py`

### Common Operations

**Check Bot State:**
```bash
python -m newtrade.binance_ta_bot --mode status
```

**Run Tests for Specific Component:**
```bash
# Test strategy components
pytest tests/test_multi_tf_strategy.py
pytest tests/test_ema_crossover.py
pytest tests/test_rsi_filter.py
pytest tests/test_volume_filter.py

# Test risk management
pytest tests/test_risk_manager.py
pytest tests/test_circuit_breaker.py
pytest tests/test_liquidation_guard.py

# Test execution
pytest tests/test_order_executor.py
pytest tests/test_exchange_client.py
```

**Quick Architecture Overview:**
```bash
# See core components
ls -la core/

# See strategy components  
ls -la strategy/

# See risk management
ls -la risk/
```

### Best Practices for Token Efficiency

1. **Use predefined commands** - Reference the quick commands above instead of typing them out
2. **Leverage tab completion** - Use shell tab completion for file paths and command options
3. **Chain related operations** - Combine commands when logical (e.g., check config then run tests)
4. **Use --verbose sparingly** - Only enable debug logging when troubleshooting specific issues
5. **Leverage existing test patterns** - Follow the naming convention `tests/test_<component>.py` for finding tests

### Troubleshooting Common Issues

**Bot won't start:**
- Check API keys are set: `echo $BINANCE_API_KEY`
- Verify config file exists and is valid YAML
- Check dependencies are installed: `pip list | grep -E "ccxt|loguru|pyyaml"`

**Tests failing:**
- Run specific test to isolate issue: `pytest tests/test_specific_component.py -v`
- Check if mock fixtures are working properly in `tests/conftest.py`
- Ensure environment variables are set for integration tests

**Configuration issues:**
- Validate YAML syntax: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
- Check for missing required sections in config.yaml
- Verify timeframe values match Binance-supported intervals (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)

## Examples

### Example 1: Quick Testing Cycle
```
# 1. Check current bot state
/binance-bot-ops status

# 2. Run strategy tests  
/binance-bot-ops test strategy

# 3. If tests pass, run bot in dry-run mode
/binance-bot-ops run dry-run

# 4. Check for any errors in output
```

### Example 2: Configuration Change Workflow
```
# 1. Backup current config
cp config.yaml config.yaml.backup

# 2. Make changes to config.yaml
# (use your editor)

# 3. Validate config is still valid YAML
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# 4. Run tests to ensure changes don't break anything
pytest

# 5. If tests pass, proceed with running bot
```

## Advanced Usage

For repetitive tasks, consider creating command aliases:
```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc)
alias bb-status="python -m newtrade.binance_ta_bot --mode status"
alias bb-run="python -m newtrade.binance_ta_bot --mode execute"
alias bb-test="pytest"
alias bb-test-unit="pytest tests/"
alias bb-test-integration="pytest tests/integration/"
```

See [reference.md](reference.md) for detailed command references and advanced troubleshooting guides.