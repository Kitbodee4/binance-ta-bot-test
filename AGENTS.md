# Agent Guidance for Binance TA Bot

## Essential Commands
- Run bot (dry-run): `python3 __main__.py`
- Live trading: `python3 __main__.py --mode execute`
- Check bot state: `python3 __main__.py --mode status`
- Debug logging: `python3 __main__.py --verbose`
- Custom config: `python3 __main__.py --config <path>`
- CLI script: `binance-ta-bot` (installed via pip)

## Testing
- Run all tests: `pytest`
- Specific test module: `pytest tests/test_<module>.py`
- Integration tests: `pytest tests/integration/`

## Setup Requirements
1. Copy `.env.example` to `.env`
2. Add `BINANCE_API_KEY` and `BINANCE_SECRET` to `.env`
3. Install dependencies: `pip install -e .` (or `pip install .`)

## Architecture Overview
- Entry point: `__main__.py` → `main:main()`
- Core flow: scanner → strategy → risk → execution
- Key files:
  - Orchestration: `core/bot_engine.py`
  - Exchange: `core/exchange_client.py` (CCXT/Binance)
  - State: `core/state_manager.py` (JSON persistence)
  - Strategy components: `strategy/ema_crossover.py`, `strategy/rsi_filter.py`, `strategy/volume_filter.py`
  - Utilities: `utils/helpers.py`, `utils/logger.py`, `utils/trade_log.py`

## Configuration
- Primary config: `config.yaml` (all sections)
- CLI overrides: `--mode`, `--dry-run`, `--config`, `--verbose`
- Environment variables: API keys (from `.env`)
- Default state file: `state_ta_bot.json` (can be overridden in config)