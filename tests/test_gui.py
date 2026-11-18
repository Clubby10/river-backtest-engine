import unittest
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock, patch

from river_backtest.config import GUI_CONFIG
from river_backtest.gui import BacktestGUI


class GuiTests(unittest.TestCase):
    def test_form_snapshot_is_independent_of_later_widget_edits(self):
        def value(text):
            return Mock(get=Mock(return_value=text))

        app = SimpleNamespace(
            defaults=GUI_CONFIG,
            asset_rows=[{"ticker_var": value(" aaa "), "alloc_var": value("2")}],
            inputs={
                key: value(text)
                for key, text in {
                    "start_date": "2024-01-01",
                    "initial_capital": "1000",
                    "commission": "2",
                    "slippage": "0.001",
                    "position_size": "0.5",
                    "kelly_p": "",
                    "kelly_b": "",
                    "kelly_lookback": "",
                    "kelly_min_trades": "10",
                    "stop_loss_pct": "25%",
                    "take_profit_pct": "50",
                    "max_drawdown_cutoff_pct": "",
                }.items()
            },
            strategy_var=value("SMA Crossover"),
            sma_short=value("5"),
            sma_long=value("15"),
            use_rolling_kelly=value(True),
        )
        app._optional_float = lambda text: BacktestGUI._optional_float(app, text)
        app._optional_pct = lambda text: BacktestGUI._optional_pct(app, text)
        config = BacktestGUI._collect_config(app)
        app.asset_rows[0]["ticker_var"].get.return_value = "BBB"
        app.inputs["initial_capital"].get.return_value = "9999"
        self.assertEqual(config.tickers, ["AAA"])
        self.assertEqual(config.allocations, {"AAA": 1})
        self.assertEqual(config.initial_capital, 1000)
        self.assertEqual(config.stop_loss_pct, 0.25)
        self.assertEqual(config.take_profit_pct, 0.5)
        self.assertIsNone(config.kelly_lookback)
        self.assertIsNone(config.max_drawdown_cutoff_pct)

    def test_add_after_removal_keeps_identifiers_and_grid_rows_unique(self):
        app = SimpleNamespace(
            _next_asset_row_id=0,
            asset_rows=[],
            asset_rows_container=object(),
        )
        app._add_asset_row = lambda *args: BacktestGUI._add_asset_row(app, *args)
        app._remove_asset_row = lambda row: BacktestGUI._remove_asset_row(app, row)
        with (
            patch("river_backtest.gui.ctk.StringVar", side_effect=lambda **kwargs: Mock()),
            patch("river_backtest.gui.ctk.CTkEntry", side_effect=lambda *args, **kwargs: Mock()),
            patch("river_backtest.gui.ctk.CTkButton", side_effect=lambda *args, **kwargs: Mock()),
        ):
            for ticker in ["AAA", "BBB", "CCC"]:
                app._add_asset_row(ticker, "1")
            app._remove_asset_row(2)
            app._add_asset_row("DDD", "1")
        self.assertEqual([row["id"] for row in app.asset_rows], [1, 3, 4])
        self.assertEqual(
            [row["ticker_entry"].grid.call_args.kwargs["row"] for row in app.asset_rows],
            [1, 3, 4],
        )

    def test_enter_adds_empty_row_without_using_event_as_ticker(self):
        app = SimpleNamespace(
            _next_asset_row_id=0,
            asset_rows=[],
            asset_rows_container=object(),
            _add_asset_row=Mock(),
            _remove_asset_row=Mock(),
        )
        with (
            patch("river_backtest.gui.ctk.StringVar"),
            patch("river_backtest.gui.ctk.CTkEntry"),
            patch("river_backtest.gui.ctk.CTkButton"),
        ):
            BacktestGUI._add_asset_row(app)
        callback = app.asset_rows[0]["ticker_entry"].bind.call_args.args[1]
        callback(object())
        app._add_asset_row.assert_called_once_with()

    def test_worker_error_survives_until_ui_handles_it(self):
        app = SimpleNamespace(
            _backtest_messages=Queue(),
            status_var=Mock(),
            run_btn=Mock(),
        )
        with patch("river_backtest.gui.run_backtest", side_effect=ValueError("No prices")):
            BacktestGUI._run_backtest(app, GUI_CONFIG)
        with patch("river_backtest.gui.messagebox.showerror") as show_error:
            BacktestGUI._poll_backtest(app)
            show_error.assert_called_once_with("Backtest Error", "No prices")
        app.run_btn.configure.assert_called_once_with(state="normal")

    def test_worker_delivers_results_without_touching_widgets(self):
        result = {"metrics": {"total_return_pct": 2}}
        app = SimpleNamespace(_backtest_messages=Queue())
        with patch("river_backtest.gui.run_backtest", return_value=result):
            BacktestGUI._run_backtest(app, GUI_CONFIG)
        tickers, received, error = app._backtest_messages.get_nowait()
        self.assertEqual(tickers, GUI_CONFIG.tickers)
        self.assertIs(received, result)
        self.assertIsNone(error)
