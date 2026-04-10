# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Development Commands
- Run bot (dry-run): `python -m newtrade.binance_ta_bot`
- Live mode: `python -m newtrade.binance_ta_bot --mode execute`
- Show state: `python -m newtrade.binance_ta_bot --mode status`
- Custom config: `python -m newtrade.binance_ta_bot --config <path>`
- Debug logging: `python -m newtrade.binance_ta_bot --verbose`
- Test: `pytest` (all), `pytest tests/test_<module>.py` (specific), `pytest tests/integration/` (integration)
- Setup: Copy `.env.example` to `.env`, add `BINANCE_API_KEY` and `BINANCE_SECRET`

## Code Architecture
**Core:** `bot_engine.py` (orchestration), `exchange_client.py` (CCXT/Binance), `state_manager.py` (JSON persistence)
**Flow:** 
1. `scanner/pair_scanner.py` (volume-based pair selection)
2. `strategy/multi_tf_strategy.py` (EMA/RSI/volume across timeframes)
3. `risk/risk_manager.py` (sizing, leverage, loss limits)
4. `risk/circuit_breaker.py` (flash crash detection/halt)
5. `risk/liquidation_guard.py` (liquidation monitoring/auto-close)
6. `execution/order_executor.py` (slippage-protected execution)

**Config:** `config.yaml` (all sections), CLI flags (`--mode`, `--dry-run`, `--config`, `--verbose`), env vars (API keys)
**Key:** `__main__.py` → `main.py:main()`, strategy components (`ema_crossover.py`, `rsi_filter.py`, `volume_filter.py`), utilities (`helpers.py`, `logger.py`, `trade_log.py`)