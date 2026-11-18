import importlib
import unittest
from dataclasses import replace
from unittest.mock import patch

import pandas as pd

from river_backtest.config import CONFIG, GUI_CONFIG, BacktestConfig
from river_backtest.service import run_backtest


class ConfigTests(unittest.TestCase):
    def test_normalization_copies_portfolio_and_preserves_order(self):
        config = BacktestConfig(tickers=[" bbb ", "AAA", "bbb"], allocations={"aaa": 1, "bbb": 3})
        result = config.validated()
        self.assertEqual(result.tickers, ["BBB", "AAA"])
        self.assertEqual(result.allocations, {"BBB": 0.75, "AAA": 0.25})
        result.tickers.append("CCC")
        result.allocations["AAA"] = 0
        self.assertEqual(config.tickers, [" bbb ", "AAA", "bbb"])
        self.assertEqual(config.allocations, {"aaa": 1, "bbb": 3})

    def test_default_difference_is_explicit(self):
        self.assertEqual(GUI_CONFIG, replace(CONFIG, max_drawdown_cutoff_pct=None))

    def test_invalid_settings_fail_before_downloading(self):
        cases = [
            {"tickers": []},
            {"initial_capital": 0},
            {"commission": -1},
            {"slippage": float("nan")},
            {"position_size": 2},
            {"kelly_min_trades": 0},
            {"kelly_lookback": 0},
            {"stop_loss_pct": 1},
            {"take_profit_pct": -0.1},
            {"max_drawdown_cutoff_pct": 1},
            {"kelly_p": 0.5},
            {"kelly_p": 0.5, "kelly_b": float("inf")},
            {"start_date": "not-a-date"},
            {"strategy": "Unknown"},
            {"short_window": 0},
            {"long_window": -1},
            {"strategy": "RSI Reversion", "rsi_period": 1},
            {"allocations": {"AAPL": float("nan"), "MSFT": 1, "NVDA": 1}},
        ]
        with patch("river_backtest.service.download_prices") as download:
            for values in cases:
                with self.subTest(values=values), self.assertRaises(ValueError):
                    run_backtest(replace(CONFIG, **values))
            download.assert_not_called()

    def test_cli_import_does_not_start_backtest(self):
        with patch("river_backtest.service.run_backtest") as run:
            importlib.import_module("run_backtest")
            run.assert_not_called()

    def test_service_runs_both_strategies_with_normalized_portfolio(self):
        close = [10, 11, 12, 9, 8, 11, 14, 10, 7, 12] * 4
        data = pd.DataFrame(
            {column: close for column in ["Open", "High", "Low", "Close"]},
            index=pd.date_range("2024-01-01", periods=len(close)),
        )
        for strategy in ["SMA Crossover", "RSI Reversion"]:
            with self.subTest(strategy=strategy):
                config = replace(
                    CONFIG,
                    strategy=strategy,
                    tickers=[" aaa "],
                    allocations={"aaa": 2},
                    short_window=2,
                    long_window=4,
                    rsi_period=2,
                )
                with patch(
                    "river_backtest.service.download_prices", return_value={"AAA": data}
                ) as download:
                    results = run_backtest(config, show_download_progress=True)
                download.assert_called_once_with(["AAA"], config.start_date, True)
                self.assertEqual(len(results["equity_curve"]), len(data))
                self.assertFalse(results["trades"].empty)
                self.assertEqual(results["metrics"]["num_trades"], len(results["trades"]))
