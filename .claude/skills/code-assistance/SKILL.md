---
name: code-assistance
description: Helps users understand, navigate, and work with codebases by explaining structure, finding components, and suggesting modifications. Use when exploring codebases, understanding architecture, or needing guidance on where to make changes.
---

# Code Assistance Skill

This Skill helps Claude Code users understand, navigate, and work with codebases more effectively by providing structural explanations, component location guidance, and modification suggestions.

## When to use this Skill

Use this Skill when:
- You want to understand how a codebase is structured
- You need to find specific files, functions, or components
- You're exploring how different parts of the codebase interact
- You need guidance on where to make changes for new features
- You're trying to understand the architecture or design patterns
- You want to follow SDLC best practices for code modifications

## Quick start

Ask questions like:
- "How does the Binance TA bot work?"
- "Where is the pair scanner located?"
- "Explain the risk management flow"
- "Where should I add a new technical indicator?"

## Instructions

### Step 1: Understand the user's question
- Determine what aspect of the codebase they want to understand
- Identify if they're asking about structure, functionality, or modification guidance
- Note any specific components or features they mention

### Step 2: Explore the codebase structure
- Use Glob and Grep to find relevant files and directories
- Look for existing patterns and conventions
- Check configuration files for setup information
- Identify the main entry points and core modules

### Step 3: Explain codebase organization
- Describe the overall architecture (layers, modules, components)
- Explain how data flows between different parts
- Highlight key design patterns used
- Reference specific file paths and line numbers

### Step 4: Provide component location guidance
- Give exact file paths when asked where to find something
- Explain what each file or module does
- Show how components relate to each other
- Mention any important configuration or setup files

### Step 5: Suggest modification locations
- Identify where to add new functionality based on existing patterns
- Reference similar implementations for guidance
- Consider SDLC phases (planning, implementation, testing)
- Suggest where tests should be added or modified
- Point out any configuration changes needed

### Step 6: Follow SDLC best practices
- Recommend planning before implementation
- Suggest writing tests for new functionality
- Advise on following existing code style and conventions
- Mention any validation or verification steps
- Encourage incremental changes with proper testing

## Examples

### Example 1: Understanding the bot structure
**Question**: "How does the Binance TA bot work?"
**Response**: 
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

### Example 2: Finding specific components
**Question**: "Where is the RSI filter implemented?"
**Response**:
The RSI filter is implemented in `strategy/rsi_filter.py`. Key elements:
- Line 15: RSI calculation function
- Line 32: Overbought/oversold logic
- Line 45: Filter application method
- Used by: `strategy/multi_tf_strategy.py` in the strategy composition

### Example 3: Adding new functionality
**Question**: "Where should I add a new MACD indicator?"
**Response**:
To add a MACD indicator:
1. Create `strategy/macd_filter.py` following the pattern of existing filters
2. Add MACD calculation and signal generation logic
3. Import and integrate in `strategy/multi_tf_strategy.py`
4. Add configuration parameters to `config.yaml` under strategy section
5. Update tests in `tests/test_macd_filter.py`
6. Follow the same structure as `rsi_filter.py` or `ema_crossover.py`

## Best practices

- **Always provide specific file paths** - Include exact locations when referencing code
- **Explain your reasoning** - Tell users why you're suggesting a particular approach
- **Reference existing patterns** - Show how similar functionality is implemented
- **Consider the full lifecycle** - Mention testing, configuration, and documentation needs
- **Follow project conventions** - Use the same coding style and patterns as existing code
- **Keep explanations actionable** - Focus on what the user can do next
- **Mention SDLC phases** - Reference planning, implementation, testing when relevant

## Requirements

No special dependencies beyond what's already required for the project:
- Python 3.x
- Standard library modules
- Project dependencies listed in requirements or setup files

## Advanced usage

For complex codebase exploration:
- Ask about specific data flows between components
- Request explanations of design patterns used
- Inquire about extension points for new features
- Seek guidance on refactoring opportunities
- Request help understanding configuration options

See [reference.md](reference.md) for detailed references on project structure and conventions.