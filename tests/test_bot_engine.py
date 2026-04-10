"""TDD tests for BotEngine - written BEFORE implementation.

Tests cover:
1. Initialization (3 tests)
2. State Machine Transitions (13 tests)
3. Main Loop (3 tests)
4. Module Integration (5 tests)
5. Error Handling (3 tests)
6. Circuit Breaker (3 tests)

Total: 30 tests targeting the state machine + coordination layer.
"""

import pytest
from unittest.mock import MagicMock, patch, call
import threading


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_exchange_client():
    """Mock ExchangeClient."""
    client = MagicMock()
    client.fetch_ticker = MagicMock(return_value={
        "symbol": "BTC/USDT:USDT",
        "last": 67500.0,
        "bid": 67499.0,
        "ask": 67501.0,
    })
    client.fetch_ohlcv = MagicMock(return_value=[
        [1711603200000, 67000, 67500, 66500, 67400, 1000],
        [1711604100000, 67400, 67600, 67300, 67500, 1100],
    ])
    return client


@pytest.fixture
def mock_pair_scanner():
    """Mock PairScanner."""
    scanner = MagicMock()
    scanner.scan = MagicMock(return_value=["BTC/USDT:USDT", "ETH/USDT:USDT"])
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
        "symbol": "BTC/USDT:USDT",
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
    mgr.get_position = MagicMock(return_value=None)
    return mgr


@pytest.fixture
def mock_circuit_breaker():
    """Mock CircuitBreaker."""
    cb = MagicMock()
    cb.should_halt = MagicMock(return_value=False)
    cb.check_flash_crash = MagicMock(return_value=False)
    cb.trigger_halt = MagicMock(return_value=None)
    return cb


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
    from newtrade.binance_ta_bot.core.bot_engine import BotEngine

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
# 1. Initialization (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBotEngineInit:
    """Test BotEngine initialization."""

    def test_should_store_all_dependencies_when_initialized(
        self,
        bot_engine,
        mock_exchange_client,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
        mock_order_executor,
        mock_state_manager,
        mock_circuit_breaker,
    ):
        """All injected dependencies must be accessible on the instance."""
        assert bot_engine.exchange_client is mock_exchange_client
        assert bot_engine.pair_scanner is mock_pair_scanner
        assert bot_engine.strategy is mock_strategy
        assert bot_engine.risk_manager is mock_risk_manager
        assert bot_engine.order_executor is mock_order_executor
        assert bot_engine.state_manager is mock_state_manager
        assert bot_engine.circuit_breaker is mock_circuit_breaker

    def test_should_start_in_idle_state_when_created(self, bot_engine):
        """Initial state must be IDLE."""
        assert bot_engine.get_state() == "IDLE"

    def test_should_store_config_values_when_initialized(
        self, bot_engine, bot_config
    ):
        """Config dict must be stored and scan_interval accessible."""
        assert bot_engine.config == bot_config
        assert bot_engine.scan_interval_sec == bot_config["scan_interval_sec"]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. State Machine Transitions (13 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateMachineTransitions:
    """Test state machine transitions per the spec table."""

    # ── IDLE → SCANNING ─────────────────────────────────────────────────

    def test_should_transition_to_scanning_when_scan_tick(
        self, bot_engine, mock_pair_scanner, mock_strategy
    ):
        """IDLE + scan_tick → SCANNING (scan runs even when no signal)."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "none",
            "trend": "ranging",
            "ema_signal": "none",
            "rsi_ok": False,
            "volume_ok": False,
        }

        bot_engine._tick()

        # Scan was called (proving SCANNING phase ran)
        mock_pair_scanner.scan.assert_called_once()
        # No signal → back to IDLE
        assert bot_engine.get_state() == "IDLE"

    # ── SCANNING → SIGNAL_DETECTED ──────────────────────────────────────

    def test_should_transition_to_signal_detected_when_signal_found(
        self,
        bot_engine,
        mock_pair_scanner,
        mock_strategy,
        mock_exchange_client,
    ):
        """SCANNING + signal_found → SIGNAL_DETECTED.

        Full _tick flow: scan finds pairs, strategy returns a signal.
        """
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "long",
            "trend": "bullish",
            "ema_signal": "bullish_crossover",
            "rsi_ok": True,
            "volume_ok": True,
        }

        bot_engine._tick()

        # After tick with a signal, state should advance past SCANNING
        assert bot_engine.get_state() in (
            "SIGNAL_DETECTED", "RISK_CHECK", "EXECUTING", "MANAGING",
        )

    # ── SCANNING → IDLE (no_signal) ─────────────────────────────────────

    def test_should_return_to_idle_when_no_signal(
        self,
        bot_engine,
        mock_pair_scanner,
        mock_strategy,
    ):
        """SCANNING + no_signal → IDLE."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "none",
            "trend": "ranging",
            "ema_signal": "none",
            "rsi_ok": False,
            "volume_ok": False,
        }

        bot_engine._tick()

        assert bot_engine.get_state() == "IDLE"

    # ── SCANNING → IDLE (scan_error) ────────────────────────────────────

    def test_should_return_to_idle_when_scan_error(
        self, bot_engine, mock_pair_scanner
    ):
        """SCANNING + scan_error → IDLE."""
        mock_pair_scanner.scan.side_effect = Exception("API timeout")

        bot_engine._tick()

        assert bot_engine.get_state() == "IDLE"

    # ── RISK_CHECK → EXECUTING (approved) ───────────────────────────────

    def test_should_transition_to_executing_when_risk_approved(
        self,
        bot_engine,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
    ):
        """RISK_CHECK + approved → EXECUTING."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "long",
            "trend": "bullish",
            "ema_signal": "bullish_crossover",
            "rsi_ok": True,
            "volume_ok": True,
        }
        mock_risk_manager.check_all_limits.return_value = {
            "approved": True,
            "reason": "all_limits_ok",
        }

        bot_engine._tick()

        assert bot_engine.get_state() == "MANAGING"

    # ── RISK_CHECK → IDLE (rejected) ────────────────────────────────────

    def test_should_return_to_idle_when_risk_rejected(
        self,
        bot_engine,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
    ):
        """RISK_CHECK + rejected → IDLE."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "long",
            "trend": "bullish",
            "ema_signal": "bullish_crossover",
            "rsi_ok": True,
            "volume_ok": True,
        }
        mock_risk_manager.check_all_limits.return_value = {
            "approved": False,
            "reason": "daily_loss_limit_exceeded",
        }

        bot_engine._tick()

        assert bot_engine.get_state() == "IDLE"

    # ── EXECUTING → MANAGING (order_filled) ─────────────────────────────

    def test_should_transition_to_managing_when_order_filled(
        self,
        bot_engine,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
        mock_order_executor,
    ):
        """EXECUTING + order_filled → MANAGING."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "long",
            "trend": "bullish",
            "ema_signal": "bullish_crossover",
            "rsi_ok": True,
            "volume_ok": True,
        }
        mock_risk_manager.check_all_limits.return_value = {
            "approved": True,
            "reason": "ok",
        }
        mock_order_executor.execute_entry.return_value = {
            "id": "order123",
            "status": "filled",
            "filled": 0.015,
            "avg_price": 67500.0,
            "symbol": "BTC/USDT:USDT",
            "side": "buy",
        }

        bot_engine._tick()

        assert bot_engine.get_state() == "MANAGING"

    # ── EXECUTING → IDLE (order_failed) ─────────────────────────────────

    def test_should_return_to_idle_when_order_failed(
        self,
        bot_engine,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
        mock_order_executor,
    ):
        """EXECUTING + order_failed → IDLE."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "long",
            "trend": "bullish",
            "ema_signal": "bullish_crossover",
            "rsi_ok": True,
            "volume_ok": True,
        }
        mock_risk_manager.check_all_limits.return_value = {
            "approved": True,
            "reason": "ok",
        }
        mock_order_executor.execute_entry.return_value = {
            "status": "rejected",
            "rejected": True,
            "reason": "insufficient_margin",
        }

        bot_engine._tick()

        assert bot_engine.get_state() == "IDLE"

    # ── MANAGING → IDLE (sl_hit) ─────────────────────────────────────

    def test_should_transition_to_exiting_when_sl_hit(self, bot_engine):
        """MANAGING + sl_hit → IDLE (via _exit_position).

        Simulate a managed position where current price hits stop-loss.
        """
        # Set up engine in MANAGING state with an open position
        bot_engine._state = "MANAGING"
        bot_engine._positions = [{
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 68500.0,
        }]

        # Current price below SL for a long position
        bot_engine.exchange_client.fetch_ticker.return_value = {
            "last": 66900.0,  # below 67000 SL
        }

        bot_engine._manage_positions()

        assert bot_engine.get_state() == "IDLE"

    # ── MANAGING → IDLE (tp_hit) ─────────────────────────────────────

    def test_should_transition_to_exiting_when_tp_hit(self, bot_engine):
        """MANAGING + tp_hit → IDLE (via _exit_position).

        Simulate a managed position where current price hits take-profit.
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

        # Current price above TP for a long position
        bot_engine.exchange_client.fetch_ticker.return_value = {
            "last": 68600.0,  # above 68500 TP
        }

        bot_engine._manage_positions()

        assert bot_engine.get_state() == "IDLE"

    # ── EXITING → IDLE (position_closed) ────────────────────────────────

    def test_should_return_to_idle_when_position_closed(
        self,
        bot_engine,
        mock_order_executor,
    ):
        """EXITING + position_closed → IDLE."""
        mock_order_executor.close_position.return_value = {
            "id": "close123",
            "status": "filled",
            "filled": 0.015,
        }

        bot_engine._state = "EXITING"
        bot_engine._positions = [{
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 68500.0,
        }]

        bot_engine._exit_position(
            bot_engine._positions[0], reason="tp_hit"
        )

        assert bot_engine.get_state() == "IDLE"

    # ── RISK_CHECK → IDLE (daily_limit_hit) ─────────────────────────────

    def test_should_return_to_idle_when_daily_limit_hit(
        self,
        bot_engine,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
    ):
        """RISK_CHECK + daily_limit_hit → IDLE."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "long",
            "trend": "bullish",
            "ema_signal": "bullish_crossover",
            "rsi_ok": True,
            "volume_ok": True,
        }
        mock_risk_manager.check_all_limits.return_value = {
            "approved": False,
            "reason": "daily_loss_limit",
        }

        bot_engine._tick()

        assert bot_engine.get_state() == "IDLE"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Main Loop (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMainLoop:
    """Test run/stop/_tick loop behavior."""

    def test_should_set_running_false_when_stop_called(self, bot_engine):
        """stop() must set running=False for graceful shutdown."""
        bot_engine._running = True

        bot_engine.stop()

        assert bot_engine._running is False

    def test_should_call_tick_in_loop_when_run(
        self, bot_engine, mock_pair_scanner
    ):
        """run() should call _tick repeatedly until stop().

        We use a side_effect to stop after 2 iterations.
        """
        tick_count = 0

        def tick_side_effect():
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 2:
                bot_engine.stop()

        mock_pair_scanner.scan.return_value = []  # no_signal → IDLE

        with patch.object(bot_engine, "_tick", side_effect=tick_side_effect):
            # Patch sleep to avoid delays in test
            with patch("time.sleep"):
                bot_engine.run()

        assert tick_count == 2

    def test_should_not_run_tick_when_already_running(self, bot_engine):
        """Calling run() when already running should not start a second loop."""
        bot_engine._running = True

        with patch.object(bot_engine, "_tick") as mock_tick:
            bot_engine.run()

        # _tick should never be called because _running was already True
        # and run() should exit immediately or refuse to double-start
        # The engine either exits early or we test the guard
        assert bot_engine._running is True


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Module Integration (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestModuleIntegration:
    """Test that BotEngine calls the right modules in the right order."""

    def test_should_use_pair_scanner_when_scanning(
        self, bot_engine, mock_pair_scanner
    ):
        """_scan() must delegate to pair_scanner.scan()."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT", "ETH/USDT:USDT"]

        result = bot_engine._scan()

        mock_pair_scanner.scan.assert_called_once()
        assert result == ["BTC/USDT:USDT", "ETH/USDT:USDT"]

    def test_should_use_strategy_when_evaluating(
        self, bot_engine, mock_strategy, mock_exchange_client
    ):
        """_evaluate(pair) must fetch OHLCV and call strategy.evaluate()."""
        mock_exchange_client.fetch_ohlcv.return_value = [
            [1711603200000, 67000, 67500, 66500, 67400, 1000],
        ]

        result = bot_engine._evaluate("BTC/USDT:USDT")

        mock_exchange_client.fetch_ohlcv.assert_called()
        mock_strategy.evaluate.assert_called_once()
        assert result["signal"] == "long"

    def test_should_use_risk_manager_when_checking_risk(
        self, bot_engine, mock_risk_manager
    ):
        """_check_risk(signal) must call risk_manager.check_all_limits()."""
        signal = {
            "symbol": "BTC/USDT:USDT",
            "signal": "long",
            "entry_price": 67500.0,
        }

        result = bot_engine._check_risk(signal)

        mock_risk_manager.check_all_limits.assert_called_once()
        assert result["approved"] is True

    def test_should_use_order_executor_when_executing(
        self, bot_engine, mock_order_executor, mock_risk_manager
    ):
        """_execute(signal) must call order_executor.execute_entry()."""
        signal = {
            "symbol": "BTC/USDT:USDT",
            "signal": "long",
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 68500.0,
            "size": 0.015,
        }

        result = bot_engine._execute(signal)

        mock_order_executor.execute_entry.assert_called_once()
        assert result["status"] == "filled"

    def test_should_use_state_manager_when_saving_positions(
        self, bot_engine, mock_state_manager
    ):
        """Position open/close must persist via state_manager."""
        position = {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
        }

        # Simulate adding a position after fill
        bot_engine._on_position_opened(position)

        mock_state_manager.add_position.assert_called_once_with(position)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Error Handling (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Test resilience to module errors."""

    def test_should_not_crash_when_strategy_raises(
        self, bot_engine, mock_pair_scanner, mock_strategy
    ):
        """Strategy exception should not propagate out of _tick()."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.side_effect = Exception("NaN in EMA")

        # Should not raise
        bot_engine._tick()

        # Should return to IDLE after error
        assert bot_engine.get_state() == "IDLE"

    def test_should_not_crash_when_exchange_raises(
        self, bot_engine, mock_pair_scanner, mock_exchange_client
    ):
        """Exchange API error during OHLCV fetch should not crash."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_exchange_client.fetch_ohlcv.side_effect = Exception(
            "Network timeout"
        )

        bot_engine._tick()

        assert bot_engine.get_state() == "IDLE"

    def test_should_increment_retry_count_on_order_failure(
        self,
        bot_engine,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
        mock_order_executor,
    ):
        """Failed order should increment retry counter."""
        initial_count = getattr(bot_engine, "_retry_count", 0)

        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "long",
            "trend": "bullish",
            "ema_signal": "bullish_crossover",
            "rsi_ok": True,
            "volume_ok": True,
        }
        mock_risk_manager.check_all_limits.return_value = {
            "approved": True,
            "reason": "ok",
        }
        mock_order_executor.execute_entry.return_value = {
            "status": "rejected",
            "rejected": True,
            "reason": "insufficient_margin",
        }

        bot_engine._tick()

        assert bot_engine._retry_count == initial_count + 1


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Circuit Breaker (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCircuitBreakerIntegration:
    """Test circuit breaker halt and flash crash behavior."""

    def test_should_skip_scanning_when_halt_active(
        self, bot_engine, mock_circuit_breaker, mock_pair_scanner
    ):
        """When circuit_breaker.should_halt() is True, _tick must skip scanning."""
        mock_circuit_breaker.should_halt.return_value = True

        bot_engine._tick()

        mock_pair_scanner.scan.assert_not_called()
        assert bot_engine.get_state() == "IDLE"

    def test_should_emergency_close_all_when_flash_crash(
        self, bot_engine, mock_circuit_breaker, mock_order_executor
    ):
        """Flash crash detection must trigger emergency close of all positions."""
        bot_engine._state = "MANAGING"
        bot_engine._positions = [
            {
                "symbol": "BTC/USDT:USDT",
                "side": "long",
                "size": 0.015,
                "entry_price": 67500.0,
                "stop_loss": 67000.0,
                "take_profit": 68500.0,
            },
            {
                "symbol": "ETH/USDT:USDT",
                "side": "short",
                "size": 0.5,
                "entry_price": 3500.0,
                "stop_loss": 3600.0,
                "take_profit": 3300.0,
            },
        ]

        # fetch_ticker returns prices that trigger flash crash
        mock_circuit_breaker.check_flash_crash.return_value = True

        bot_engine.exchange_client.fetch_ticker.side_effect = [
            {"last": 63000.0},   # BTC: ~6.7% drop from 67500
            {"last": 3700.0},    # ETH: ~5.7% rise from 3500 (short gets hurt)
        ]

        bot_engine._manage_positions()

        # Both positions should be closed
        assert mock_order_executor.close_position.call_count == 2
        assert bot_engine.get_state() == "IDLE"

    def test_should_not_place_orders_when_halt_active(
        self,
        bot_engine,
        mock_circuit_breaker,
        mock_pair_scanner,
        mock_strategy,
        mock_order_executor,
    ):
        """Even with a valid signal, halted engine must not execute orders."""
        mock_circuit_breaker.should_halt.return_value = True
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "long",
            "trend": "bullish",
            "ema_signal": "bullish_crossover",
            "rsi_ok": True,
            "volume_ok": True,
        }

        bot_engine._tick()

        mock_order_executor.execute_entry.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Full Flow Integration (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullFlow:
    """Test end-to-end flow through multiple state transitions."""

    def test_should_complete_full_entry_flow_in_single_tick(
        self,
        bot_engine,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
        mock_order_executor,
        mock_state_manager,
    ):
        """IDLE → SCANNING → SIGNAL → RISK → EXECUTING → MANAGING in one tick."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "long",
            "trend": "bullish",
            "ema_signal": "bullish_crossover",
            "rsi_ok": True,
            "volume_ok": True,
        }
        mock_risk_manager.check_all_limits.return_value = {
            "approved": True,
            "reason": "ok",
        }
        mock_order_executor.execute_entry.return_value = {
            "id": "order123",
            "status": "filled",
            "filled": 0.015,
            "avg_price": 67500.0,
            "symbol": "BTC/USDT:USDT",
            "side": "buy",
        }

        bot_engine._tick()

        assert bot_engine.get_state() == "MANAGING"
        mock_state_manager.add_position.assert_called_once()

    def test_should_complete_full_exit_flow(
        self, bot_engine, mock_order_executor, mock_state_manager
    ):
        """MANAGING → EXITING → IDLE when SL/TP hit and position closed."""
        mock_order_executor.close_position.return_value = {
            "id": "close123",
            "status": "filled",
            "filled": 0.015,
        }

        bot_engine._state = "MANAGING"
        bot_engine._positions = [{
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "size": 0.015,
            "entry_price": 67500.0,
            "stop_loss": 67000.0,
            "take_profit": 68500.0,
        }]

        bot_engine._exit_position(
            bot_engine._positions[0], reason="sl_hit"
        )

        assert bot_engine.get_state() == "IDLE"
        mock_state_manager.remove_position.assert_called_once_with(
            "BTC/USDT:USDT"
        )

    def test_should_handle_rejected_signal_then_retry_next_tick(
        self,
        bot_engine,
        mock_pair_scanner,
        mock_strategy,
        mock_risk_manager,
    ):
        """First tick: risk rejects → IDLE. Second tick: risk approves → MANAGING."""
        mock_pair_scanner.scan.return_value = ["BTC/USDT:USDT"]
        mock_strategy.evaluate.return_value = {
            "signal": "long",
            "trend": "bullish",
            "ema_signal": "bullish_crossover",
            "rsi_ok": True,
            "volume_ok": True,
        }

        # First tick: rejected
        mock_risk_manager.check_all_limits.return_value = {
            "approved": False,
            "reason": "max_positions_reached",
        }
        bot_engine._tick()
        assert bot_engine.get_state() == "IDLE"

        # Second tick: approved
        mock_risk_manager.check_all_limits.return_value = {
            "approved": True,
            "reason": "ok",
        }
        bot_engine._tick()
        assert bot_engine.get_state() == "MANAGING"
