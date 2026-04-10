"""TDD tests for Binance TA Bot integration gaps.

These tests MUST FAIL against current code (TDD RED phase).
Each test proves a specific integration gap exists and will pass
once the gap is fixed.

Gaps covered:
  1. _manage_positions() not called in MANAGING state
  2. _check_risk() passes 1 signal dict, not 5 args
  3. _execute() passes "long"/"short" instead of "buy"/"sell"
  4. _exit_position() passes "long"/"short" instead of "buy"/"sell"
  5. _manage_positions() calls check_flash_crash(symbol, price) wrong
  6. Strategy evaluate() returns no size/entry_price/sl/tp
  7. ExchangeClient missing fetch_markets()
  8. ExchangeClient missing fetch_order() / cancel_order()
  9. BotEngine has no liquidation_guard
  10. StateManager.load() not called in _build_bot()
  11. BotEngine doesn't track equity
"""

import inspect

import pytest
from unittest.mock import MagicMock, patch, call

from newtrade.binance_ta_bot.core.bot_engine import BotEngine
from newtrade.binance_ta_bot.core.exchange_client import ExchangeClient


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_exchange_client():
    """Mock ExchangeClient."""
    client = MagicMock(spec=ExchangeClient)
    client.fetch_ticker = MagicMock(return_value={
        "symbol": "BTC/USDT:USDT",
        "last": 67500.0,
    })
    client.fetch_ohlcv = MagicMock(return_value=[
        [1711603200000, 67000, 67500, 66500, 67400, 1000],
    ])
    return client


@pytest.fixture
def mock_pair_scanner():
    """Mock PairScanner."""
    scanner = MagicMock()
    scanner.scan = MagicMock(return_value=["BTC/USDT:USDT"])
    return scanner


@pytest.fixture
def mock_strategy():
    """Mock MultiTimeframeStrategy."""
    strategy = MagicMock()
    strategy.evaluate = MagicMock(return_value={
        "signal": "long",
        "trend": "bullish",
        "ema_signal": "bullish_crossover",
        "rsi_ok": True,
        "volume_ok": True,
    })
    return strategy


@pytest.fixture
def mock_risk_manager():
    """Mock RiskManager."""
    mgr = MagicMock()
    mgr.check_all_limits = MagicMock(return_value={
        "approved": True,
        "reason": "all_limits_ok",
    })
    mgr.calculate_position_size = MagicMock(return_value=0.015)
    mgr.calculate_sl_tp = MagicMock(return_value={
        "stop_loss": 67000.0,
        "take_profit": 68500.0,
    })
    return mgr


@pytest.fixture
def mock_order_executor():
    """Mock OrderExecutor."""
    executor = MagicMock()
    executor.execute_entry = MagicMock(return_value={
        "id": "order123",
        "status": "filled",
        "filled": 0.015,
        "avg_price": 67500.0,
        "symbol": "BTC/USDT:USDT",
        "side": "buy",
    })
    executor.close_position = MagicMock(return_value={
        "id": "close123",
        "status": "filled",
        "filled": 0.015,
    })
    return executor


@pytest.fixture
def mock_state_manager():
    """Mock StateManager."""
    mgr = MagicMock()
    mgr.load = MagicMock(return_value={
        "bot_status": "idle",
        "equity": 10000.0,
        "daily_pnl": 0.0,
        "daily_trades": 0,
        "open_positions": [],
        "last_scan": None,
    })
    mgr.save = MagicMock(return_value=None)
    mgr.add_position = MagicMock(return_value=None)
    mgr.remove_position = MagicMock(return_value=None)
    return mgr


@pytest.fixture
def mock_circuit_breaker():
    """Mock CircuitBreaker."""
    cb = MagicMock()
    cb.should_halt = MagicMock(return_value=False)
    cb.check_flash_crash = MagicMock(return_value=False)
    return cb


@pytest.fixture
def mock_liquidation_guard():
    """Mock LiquidationGuard."""
    guard = MagicMock()
    guard.check = MagicMock(return_value={
        "at_risk": False,
        "distance_pct": 0.5,
        "action": "none",
    })
    return guard


@pytest.fixture
def bot_config():
    """Default bot configuration."""
    return {
        "scan_interval_sec": 60,
        "dry_run": True,
        "log_level": "INFO",
    }


@pytest.fixture
def bot_engine(
    mock_exchange_client,
    mock_pair_scanner,
    mock_strategy,
    mock_risk_manager,
    mock_order_executor,
    mock_state_manager,
    mock_circuit_breaker,
    bot_config,
):
    """Fully wired BotEngine instance with all mocked dependencies."""
    return BotEngine(
        exchange_client=mock_exchange_client,
        pair_scanner=mock_pair_scanner,
        strategy=mock_strategy,
        risk_manager=mock_risk_manager,
        order_executor=mock_order_executor,
        state_manager=mock_state_manager,
        circuit_breaker=mock_circuit_breaker,
        config=bot_config,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Gap 7: ExchangeClient missing fetch_markets()
# ═══════════════════════════════════════════════════════════════════════════════


class TestExchangeClientMissingMethods:
    """Tests for ExchangeClient missing methods (Gaps 7, 8)."""

    def test_should_have_fetch_markets_when_initialized(self):
        """ExchangeClient must expose fetch_markets() for PairScanner.

        Gap 7: PairScanner.scan() calls exchange.fetch_markets() but
        ExchangeClient has no such method.
        """
        # Verify the method exists on the class
        assert hasattr(ExchangeClient, "fetch_markets"), (
            "ExchangeClient.fetch_markets() is missing. "
            "PairScanner.scan() depends on it."
        )

    def test_should_have_fetch_order_when_initialized(self):
        """ExchangeClient must expose fetch_order() for OrderExecutor.

        Gap 8: OrderExecutor.check_order_status() calls
        exchange_client.fetch_order(order_id, symbol) but
        ExchangeClient has no such method.
        """
        assert hasattr(ExchangeClient, "fetch_order"), (
            "ExchangeClient.fetch_order() is missing. "
            "OrderExecutor.check_order_status() depends on it."
        )

    def test_should_have_cancel_order_when_initialized(self):
        """ExchangeClient must expose cancel_order() for OrderExecutor.

        Gap 8: OrderExecutor.cancel_order() calls
        exchange_client.cancel_order(order_id, symbol) but
        ExchangeClient has no such method.
        """
        assert hasattr(ExchangeClient, "cancel_order"), (
            "ExchangeClient.cancel_order() is missing. "
            "OrderExecutor.cancel_order() depends on it."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Gaps 3, 4: Side conversion helper
# ═══════════════════════════════════════════════════════════════════════════════


class TestSideConversion:
    """Tests for long/short to buy/sell conversion (Gaps 3, 4)."""

    def test_should_have_side_to_order_helper_when_initialized(self, bot_engine):
        """BotEngine must have _side_to_order() for converting signal side.

        Gap 3, 4: The engine uses "long"/"short" internally but the
        OrderExecutor expects "buy"/"sell".
        """
        assert hasattr(bot_engine, "_side_to_order"), (
            "BotEngine._side_to_order() helper is missing. "
            "Needed to convert 'long'/'short' to 'buy'/'sell'."
        )

    def test_should_return_buy_when_long(self, bot_engine):
        """_side_to_order('long') must return 'buy'."""
        result = bot_engine._side_to_order("long")
        assert result == "buy", (
            f"_side_to_order('long') returned '{result}', expected 'buy'"
        )

    def test_should_return_sell_when_short(self, bot_engine):
        """_side_to_order('short') must return 'sell'."""
        result = bot_engine._side_to_order("short")
        assert result == "sell", (
            f"_side_to_order('short') returned '{result}', expected 'sell'"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Gap 2: _check_risk() passes 5 args not 1 signal dict
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckRiskArgs:
    """Tests for _check_risk() argument passing (Gap 2)."""

    def test_should_pass_five_args_to_check_all_limits(
        self,
        bot_engine,
        mock_risk_manager,
    ):
        """_check_risk() must call check_all_limits with 5 positional args.

        Gap 2: Currently passes 1 signal dict. The RiskManager expects:
            check_all_limits(equity, daily_pnl, weekly_pnl,
                             open_positions, consecutive_losses)
        """
        signal = {
            "symbol": "BTC/USDT:USDT",
            "signal": "long",
            "entry_price": 67500.0,
        }

        bot_engine._check_risk(signal)

        # Verify check_all_limits was called
        assert mock_risk_manager.check_all_limits.called, (
            "check_all_limits() was not called"
        )

        # Verify it was called with 5 positional args, not 1
        call_args = mock_risk_manager.check_all_limits.call_args
        positional_count = len(call_args.args) if call_args.args else 0
        assert positional_count == 5, (
            f"check_all_limits() was called with {positional_count} "
            f"positional args, expected 5 "
            f"(equity, daily_pnl, weekly_pnl, open_positions, "
            f"consecutive_losses)"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Gap 3: _execute() converts side to buy/sell
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecuteConvertsSide:
    """Tests for _execute() side conversion (Gap 3)."""

    def test_should_pass_buy_to_execute_entry_when_signal_long(
        self,
        bot_engine,
        mock_order_executor,
    ):
        """_execute() must convert signal='long' to side='buy'.

        Gap 3: OrderExecutor.execute_entry() expects side='buy' or 'sell',
        not 'long' or 'short'.
        """
        signal = {
            "symbol": "BTC/USDT:USDT",
            "signal": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 68500.0,
        }

        bot_engine._execute(signal)

        # Check the side argument passed to execute_entry
        call_kwargs = mock_order_executor.execute_entry.call_args
        side_arg = call_kwargs.kwargs.get("side", call_kwargs.args[1] if len(call_kwargs.args) > 1 else None)
        assert side_arg == "buy", (
            f"_execute() passed side='{side_arg}' to execute_entry, "
            f"expected 'buy' for signal='long'"
        )

    def test_should_pass_sell_to_execute_entry_when_signal_short(
        self,
        bot_engine,
        mock_order_executor,
    ):
        """_execute() must convert signal='short' to side='sell'."""
        signal = {
            "symbol": "BTC/USDT:USDT",
            "signal": "short",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 68000.0,
            "take_profit": 66500.0,
        }

        bot_engine._execute(signal)

        call_kwargs = mock_order_executor.execute_entry.call_args
        side_arg = call_kwargs.kwargs.get("side", call_kwargs.args[1] if len(call_kwargs.args) > 1 else None)
        assert side_arg == "sell", (
            f"_execute() passed side='{side_arg}' to execute_entry, "
            f"expected 'sell' for signal='short'"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Gap 6: Signal dict must have size, entry_price, stop_loss, take_profit
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecuteComputesSizeAndPrices:
    """Tests for _execute() computing missing fields (Gap 6)."""

    def test_should_have_size_in_signal_before_execute(
        self,
        bot_engine,
        mock_order_executor,
        mock_risk_manager,
    ):
        """Signal must have size > 0 before _execute() is called.

        Gap 6: Strategy.evaluate() only returns signal/trend/filters.
        BotEngine must compute size via risk_manager.calculate_position_size()
        before calling _execute().
        """
        signal = {
            "symbol": "BTC/USDT:USDT",
            "signal": "long",
            # Note: no size, entry_price, stop_loss, take_profit
        }

        bot_engine._execute(signal)

        # execute_entry must have been called with size > 0
        call_kwargs = mock_order_executor.execute_entry.call_args
        size_arg = call_kwargs.kwargs.get("size", call_kwargs.args[2] if len(call_kwargs.args) > 2 else 0)
        assert size_arg > 0, (
            f"_execute() passed size={size_arg} to execute_entry. "
            f"Expected size > 0 (computed via risk_manager)."
        )

    def test_should_have_entry_price_in_signal_before_execute(
        self,
        bot_engine,
        mock_order_executor,
    ):
        """Signal must have entry_price > 0 before _execute() is called.

        Gap 6: BotEngine must populate entry_price from ticker or strategy.
        """
        signal = {
            "symbol": "BTC/USDT:USDT",
            "signal": "long",
        }

        bot_engine._execute(signal)

        call_kwargs = mock_order_executor.execute_entry.call_args
        price_arg = call_kwargs.kwargs.get(
            "intended_price",
            call_kwargs.args[3] if len(call_kwargs.args) > 3 else 0,
        )
        assert price_arg is not None and price_arg > 0, (
            f"_execute() passed intended_price={price_arg}. "
            f"Expected > 0 (from ticker/strategy)."
        )

    def test_should_have_stop_loss_in_signal_before_execute(
        self,
        bot_engine,
        mock_order_executor,
    ):
        """Signal must have stop_loss > 0 before _execute() is called.

        Gap 6: BotEngine must compute stop_loss via risk_manager.calculate_sl_tp().
        """
        signal = {
            "symbol": "BTC/USDT:USDT",
            "signal": "long",
        }

        bot_engine._execute(signal)

        call_kwargs = mock_order_executor.execute_entry.call_args
        sl_arg = call_kwargs.kwargs.get("stop_loss", 0)
        assert sl_arg > 0, (
            f"_execute() passed stop_loss={sl_arg}. "
            f"Expected > 0 (computed via risk_manager)."
        )

    def test_should_have_take_profit_in_signal_before_execute(
        self,
        bot_engine,
        mock_order_executor,
    ):
        """Signal must have take_profit > 0 before _execute() is called.

        Gap 6: BotEngine must compute take_profit via risk_manager.calculate_sl_tp().
        """
        signal = {
            "symbol": "BTC/USDT:USDT",
            "signal": "long",
        }

        bot_engine._execute(signal)

        call_kwargs = mock_order_executor.execute_entry.call_args
        tp_arg = call_kwargs.kwargs.get("take_profit", 0)
        assert tp_arg > 0, (
            f"_execute() passed take_profit={tp_arg}. "
            f"Expected > 0 (computed via risk_manager)."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Gap 4: _exit_position() converts side to buy/sell
# ═══════════════════════════════════════════════════════════════════════════════


class TestExitPositionConvertsSide:
    """Tests for _exit_position() side conversion (Gap 4)."""

    def test_should_pass_sell_to_close_position_when_long(
        self,
        bot_engine,
        mock_order_executor,
    ):
        """_exit_position() must convert side='long' to 'sell' for close.

        Gap 4: OrderExecutor.close_position() expects 'buy'/'sell',
        not 'long'/'short'.
        """
        position = {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 68500.0,
        }
        bot_engine._positions = [position]
        bot_engine._state = "MANAGING"

        bot_engine._exit_position(position, reason="test")

        call_kwargs = mock_order_executor.close_position.call_args
        side_arg = call_kwargs.kwargs.get(
            "side",
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None,
        )
        assert side_arg == "sell", (
            f"_exit_position() passed side='{side_arg}' to close_position, "
            f"expected 'sell' for position side='long'"
        )

    def test_should_pass_buy_to_close_position_when_short(
        self,
        bot_engine,
        mock_order_executor,
    ):
        """_exit_position() must convert side='short' to 'buy' for close."""
        position = {
            "symbol": "ETH/USDT:USDT",
            "side": "short",
            "size": 0.5,
            "entry_price": 3500.0,
            "stop_loss": 3600.0,
            "take_profit": 3300.0,
        }
        bot_engine._positions = [position]
        bot_engine._state = "MANAGING"

        bot_engine._exit_position(position, reason="test")

        call_kwargs = mock_order_executor.close_position.call_args
        side_arg = call_kwargs.kwargs.get(
            "side",
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None,
        )
        assert side_arg == "buy", (
            f"_exit_position() passed side='{side_arg}' to close_position, "
            f"expected 'buy' for position side='short'"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Gap 1: _manage_positions() is called in MANAGING state
# ═══════════════════════════════════════════════════════════════════════════════


class TestManagePositionsIsCalled:
    """Tests for _manage_positions() invocation (Gap 1)."""

    def test_should_call_manage_positions_when_state_managing(
        self,
        bot_engine,
    ):
        """In MANAGING state, _tick() must call _manage_positions().

        Gap 1: Currently _tick() just returns when state is MANAGING,
        never calling _manage_positions().
        """
        # Set up in MANAGING state with an open position
        bot_engine._state = "MANAGING"
        bot_engine._positions = [{
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 68500.0,
        }]

        with patch.object(bot_engine, "_manage_positions") as mock_manage:
            bot_engine._tick()
            mock_manage.assert_called(), (
                "_tick() in MANAGING state did not call _manage_positions(). "
                "Positions will never be monitored for SL/TP."
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Gap 5: _manage_positions() flash crash check signature
# ═══════════════════════════════════════════════════════════════════════════════


class TestManagePositionsFlashCrash:
    """Tests for _manage_positions() flash crash call (Gap 5)."""

    def test_should_call_check_flash_crash_with_entry_price_and_side(
        self,
        bot_engine,
        mock_circuit_breaker,
    ):
        """_manage_positions() must call check_flash_crash(entry_price, current_price, side).

        Gap 5: Currently calls check_flash_crash(symbol, current_price)
        but CircuitBreaker.check_flash_crash() expects
        (entry_price, current_price, side).
        """
        bot_engine._state = "MANAGING"
        bot_engine._positions = [{
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 68500.0,
        }]
        bot_engine.exchange_client.fetch_ticker.return_value = {
            "last": 67600.0,
        }

        bot_engine._manage_positions()

        # Verify check_flash_crash was called with correct args
        assert mock_circuit_breaker.check_flash_crash.called, (
            "check_flash_crash() was not called"
        )
        call_args = mock_circuit_breaker.check_flash_crash.call_args

        # Should have 3 positional args: entry_price, current_price, side
        # NOT (symbol, price)
        positional = call_args.args if call_args.args else ()
        keyword = call_args.kwargs

        # Verify first arg is entry_price (a number), not symbol (a string)
        if positional:
            first_arg = positional[0]
            assert isinstance(first_arg, (int, float)), (
                f"check_flash_crash() first arg is '{first_arg}' "
                f"(type={type(first_arg).__name__}). "
                f"Expected entry_price (float), got symbol string. "
                f"Correct signature: check_flash_crash(entry_price, current_price, side)"
            )

        # Verify 'side' keyword or positional arg exists
        has_side = "side" in keyword or len(positional) >= 3
        assert has_side, (
            "check_flash_crash() missing 'side' argument. "
            "Expected: check_flash_crash(entry_price, current_price, side)"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Gap 9: BotEngine accepts liquidation_guard
# ═══════════════════════════════════════════════════════════════════════════════


class TestBotEngineLiquidationGuard:
    """Tests for BotEngine liquidation_guard integration (Gap 9)."""

    def test_should_accept_liquidation_guard_when_initialized(
        self,
        mock_exchange_client,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
        mock_order_executor,
        mock_state_manager,
        mock_circuit_breaker,
        mock_liquidation_guard,
        bot_config,
    ):
        """BotEngine.__init__() must accept and store liquidation_guard.

        Gap 9: _build_bot() creates LiquidationGuard but never passes it
        to BotEngine.
        """
        engine = BotEngine(
            exchange_client=mock_exchange_client,
            pair_scanner=mock_pair_scanner,
            strategy=mock_strategy,
            risk_manager=mock_risk_manager,
            order_executor=mock_order_executor,
            state_manager=mock_state_manager,
            circuit_breaker=mock_circuit_breaker,
            config=bot_config,
            liquidation_guard=mock_liquidation_guard,
        )

        assert hasattr(engine, "liquidation_guard"), (
            "BotEngine does not store liquidation_guard attribute"
        )
        assert engine.liquidation_guard is mock_liquidation_guard, (
            "BotEngine.liquidation_guard is not the injected instance"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Gap 10: StateManager.load() called in _build_bot
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateManagerLoadCalled:
    """Tests for StateManager.load() wiring (Gap 10)."""

    def test_should_call_state_manager_load_in_build_bot(self):
        """_build_bot() must call state_manager.load() to restore state.

        Gap 10: _build_bot() creates StateManager but never calls .load(),
        so previous state (positions, equity, etc.) is lost on restart.
        """
        from newtrade.binance_ta_bot.main import _build_bot

        config = {
            "exchange": {"name": "binanceusdm"},
            "scanner": {},
            "strategy": {},
            "risk": {},
            "circuit_breaker": {},
            "bot": {"state_file": "/tmp/test_state.json"},
        }

        with patch("newtrade.binance_ta_bot.main.StateManager") as MockSM, \
             patch("newtrade.binance_ta_bot.main.ExchangeClient"), \
             patch("newtrade.binance_ta_bot.main.PairScanner"), \
             patch("newtrade.binance_ta_bot.main.MultiTimeframeStrategy"), \
             patch("newtrade.binance_ta_bot.main.RiskManager"), \
             patch("newtrade.binance_ta_bot.main.CircuitBreaker"), \
             patch("newtrade.binance_ta_bot.main.LiquidationGuard"), \
             patch("newtrade.binance_ta_bot.main.OrderExecutor"):

            mock_sm_instance = MagicMock()
            MockSM.return_value = mock_sm_instance

            _build_bot(config, dry_run=True)

            mock_sm_instance.load.assert_called(), (
                "_build_bot() did not call state_manager.load(). "
                "Bot will lose all state on restart."
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Gap 11: BotEngine tracks equity
# ═══════════════════════════════════════════════════════════════════════════════


class TestBotEngineTracksEquity:
    """Tests for BotEngine equity tracking (Gap 11)."""

    def test_should_have_equity_attribute_when_initialized(self, bot_engine):
        """BotEngine must have _equity attribute for risk calculations.

        Gap 11: Risk manager needs equity to compute position sizing
        and check limits. BotEngine must track current equity.
        """
        assert hasattr(bot_engine, "_equity"), (
            "BotEngine._equity attribute is missing. "
            "Risk calculations require current equity."
        )

    def test_should_load_equity_from_state_manager(
        self,
        mock_exchange_client,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
        mock_order_executor,
        mock_state_manager,
        mock_circuit_breaker,
        bot_config,
    ):
        """BotEngine must initialize _equity from state_manager.load() result.

        Gap 11: On startup, equity should be loaded from persisted state
        (or fetched from exchange if state is empty).
        """
        mock_state_manager.load.return_value = {
            "equity": 15000.0,
            "open_positions": [],
        }

        engine = BotEngine(
            exchange_client=mock_exchange_client,
            pair_scanner=mock_pair_scanner,
            strategy=mock_strategy,
            risk_manager=mock_risk_manager,
            order_executor=mock_order_executor,
            state_manager=mock_state_manager,
            circuit_breaker=mock_circuit_breaker,
            config=bot_config,
        )

        # Either _equity is set directly, or it can be retrieved
        equity = getattr(engine, "_equity", None)
        assert equity is not None and equity > 0, (
            f"BotEngine._equity is {equity}. "
            f"Expected > 0 (loaded from state_manager)."
        )
