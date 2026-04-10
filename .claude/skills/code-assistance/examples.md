# Code Assistance Examples

## Example Questions and Expected Responses

### Example 1: Basic Codebase Understanding
**User Question**: "Can you help me understand how the Binance TA bot works?"
**Expected Skill Response**:
The Binance TA bot follows a modular architecture with these core components:
- `main.py` - CLI entry point and bot lifecycle management
- `core/bot_engine.py` - Main orchestration loop that coordinates all modules
- `core/exchange_client.py` - CCXT/Binance exchange wrapper
- `core/state_manager.py` - JSON persistence for bot state
- `scanner/pair_scanner.py` - Volume-based pair selection
- `strategy/multi_tf_strategy.py` - EMA/RSI/volume strategy across timeframes
- `risk/risk_manager.py` - Position sizing, leverage, and loss limits
- `risk/circuit_breaker.py` - Flash crash detection and trading halt
- `risk/liquidation_guard.py` - Liquidation monitoring and auto-close
- `execution/order_executor.py` - Slippage-protected order execution

Data flows: Pair Scanner → Strategy → Risk Management → Order Execution

### Example 2: Finding Specific Components
**User Question**: "Where is the EMA crossover logic implemented?"
**Expected Skill Response**:
The EMA crossover logic is implemented in `strategy/ema_crossover.py`. Key elements:
- Line 12: EMA calculation function
- Line 25: Crossover detection logic
- Line 38: Signal generation method
- Used by: `strategy/multi_tf_strategy.py` in the strategy composition
- Configuration: `ema_fast` and `ema_slow` parameters in config.yaml

### Example 3: Adding New Functionality
**User Question**: "Where should I add a new Bollinger Bands indicator?"
**Expected Skill Response**:
To add a Bollinger Bands indicator:
1. Create `strategy/bollinger_bands_filter.py` following the pattern of existing filters
2. Add Bollinger Bands calculation and signal generation logic
3. Import and integrate in `strategy/multi_tf_strategy.py`
4. Add configuration parameters to `config.yaml` under strategy section (e.g., `bb_period`, `bb_std_dev`)
5. Update tests in `tests/test_bollinger_bands_filter.py`
6. Follow the same structure as `rsi_filter.py` or `ema_crossover.py`

### Example 4: Architecture Explanation
**User Question**: "Explain how risk management works in this bot"
**Expected Skill Response**:
Risk management in the Binance TA bot consists of several layers:
1. `risk/risk_manager.py` - Core risk management:
   - Position sizing based on risk_per_trade (default 1%)
   - Leverage limits (default 3x)
   - Position count limits (default 3)
   - Daily/weekly loss limits
   - Stop loss percentage constraints
2. `risk/circuit_breaker.py` - Emergency halt mechanisms:
   - Flash crash detection (default 5% drop)
   - Automatic trading halt (default 60 minutes)
   - Slippage protection
3. `risk/liquidation_guard.py` - Liquidation protection:
   - Position monitoring for liquidation risk
   - Automatic close when liquidation threshold reached
   - Warning notifications before liquidation

The risk components wrap the execution flow: Strategy signals → Risk validation → Order execution

### Example 5: Configuration Guidance
**User Question**: "How do I change the timeframe for the strategy?"
**Expected Skill Response**:
To change the strategy timeframe:
1. Edit `config.yaml` in the strategy section:
   - `entry_tf`: Entry timeframe (default: "1m")
   - `trend_tf`: Trend timeframe (default: "15m")
2. Supported Binance timeframes: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
3. Adjust related limits if needed:
   - `entry_limit`: Candles to fetch for entry timeframe (default: 1000)
   - `trend_limit`: Candles to fetch for trend timeframe (default: 1000)
4. Consider that changing timeframes may affect:
   - Signal frequency and reliability
   - Required candle history
   - Computational requirements
5. Restart the bot for changes to take effect

### Example 6: Troubleshooting Guidance
**User Question**: "The bot isn't placing any orders, where should I look?"
**Expected Skill Response**:
If the bot isn't placing orders, check these areas in order:
1. **Logs**: Look for INFO/DEBUG messages in the output
2. **Pair Scanner** (`scanner/pair_scanner.py`):
   - Are pairs being selected? Check volume filters
   - Check logs for "Selected pairs" messages
3. **Strategy** (`strategy/multi_tf_strategy.py`):
   - Are signals being generated?
   - Check EMA, RSI, and volume filter outputs
4. **Risk Management** (`risk/risk_manager.py`):
   - Are positions being blocked by risk limits?
   - Check for "risk check failed" messages
   - Verify daily/weekly loss limits aren't exceeded
5. **Order Executor** (`execution/order_executor.py`):
   - Are orders failing validation?
   - Check slippage and price validation
6. **Configuration**:
   - Verify `dry_run` setting matches your expectation
   - Check API keys are set (unless in dry-run mode)
   - Ensure minimum position sizes are met

Start by running with `--verbose` flag to see detailed logging.

## Testing the Skill

To verify the Skill is working correctly, try these test questions:

1. "What files make up the core of the bot?"
2. "Where would I look to modify the trading strategy?"
3. "How does the pair selection work?"
4. "What happens when the circuit breaker triggers?"
5. "Where is bot state saved and loaded?"

The Skill should respond with specific file paths, clear explanations, and actionable guidance.