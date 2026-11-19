"""Exercise API requests offline without downloading prices or running simulations."""

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from river_backtest.api import app
from river_backtest.config import CONFIG
from river_backtest.strategies.rsi_reversion import RSIReversion
from river_backtest.strategies.sma_crossover import SMACrossover


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))
        dates = pd.date_range("2025-01-01", periods=2, name="date")
        self.results = {
            "metrics": {
                "total_return_pct": np.float64(5.0),
                "num_trades": np.int64(1),
                "sharpe_ratio": np.nan,
            },
            "trades": pd.DataFrame(
                [{"date": dates[1], "ticker": "AAPL", "quantity": 2, "price": 100.0}]
            ),
            "equity_curve": pd.DataFrame({"equity": [10000.0, 10500.0]}, index=dates),
            "ticker_value_curve": pd.DataFrame({"AAPL": [0.0, 200.0]}, index=dates),
            "benchmark_curve": pd.DataFrame({"benchmark_equity": [10000.0, 10200.0]}, index=dates),
        }
        self.run = self.enterContext(
            patch("river_backtest.api.run_backtest", return_value=self.results)
        )
        self.download = self.enterContext(patch("river_backtest.service.download_prices"))
        self.addCleanup(self.download.assert_not_called)

    def test_health_returns_ok_without_running_backtest(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.run.assert_not_called()

    def test_strategies_exposes_metadata_without_running_backtest(self):
        response = self.client.get("/strategies")
        self.assertEqual(response.status_code, 200)
        entries = response.json()["strategies"]
        names = [entry["name"] for entry in entries]
        self.assertEqual(names, sorted(set(names)))
        by_name = {entry["name"]: entry for entry in entries}
        for cls in (SMACrossover, RSIReversion):
            self.assertEqual(
                by_name[cls.name],
                {
                    "name": cls.name,
                    "description": cls.description,
                    "default_parameters": cls.default_parameters,
                },
            )
        self.run.assert_not_called()

    def test_defaults_return_only_json_safe_metrics(self):
        response = self.client.post("/backtest", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(
            response.json(),
            {"metrics": {"total_return_pct": 5.0, "num_trades": 1, "sharpe_ratio": None}},
        )
        self.run.assert_called_once()
        config = self.run.call_args.args[0]
        self.assertEqual(config.tickers, CONFIG.tickers)
        self.assertEqual(config.initial_capital, CONFIG.initial_capital)
        self.assertEqual(config.strategy_parameters, {})
        self.assertEqual(
            config.allocations, {ticker: 1 / len(CONFIG.tickers) for ticker in CONFIG.tickers}
        )

    def test_custom_settings_are_normalized_and_forwarded_for_both_strategies(self):
        for name, parameters in [
            ("SMA Crossover", {"short_window": 5, "long_window": 15}),
            ("RSI Reversion", {"period": 7, "oversold": 25.0, "overbought": 75.0}),
        ]:
            with self.subTest(strategy=name):
                self.run.reset_mock()
                response = self.client.post(
                    "/backtest",
                    json={
                        "tickers": [" aapl ", "msft", "AAPL"],
                        "allocations": {"aapl": 3, "msft": 1},
                        "strategy": name,
                        "strategy_parameters": parameters,
                        "initial_capital": 25000,
                        "commission": 0,
                        "max_drawdown_cutoff_pct": None,
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.run.assert_called_once()
                config = self.run.call_args.args[0]
                self.assertEqual(config.tickers, ["AAPL", "MSFT"])
                self.assertEqual(config.allocations, {"AAPL": 0.75, "MSFT": 0.25})
                self.assertEqual(config.strategy, name)
                self.assertEqual(config.strategy_parameters, parameters)
                self.assertEqual(config.initial_capital, 25000)
                self.assertEqual(config.commission, 0)
                self.assertIsNone(config.max_drawdown_cutoff_pct)

    def test_details_include_trades_and_dated_curves(self):
        response = self.client.post("/backtest?include_details=true", json={})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload), set(self.results))
        self.assertEqual(payload["trades"][0]["date"], "2025-01-02T00:00:00.000")
        self.assertEqual(payload["trades"][0]["quantity"], 2)
        for key, column, expected in [
            ("equity_curve", "equity", 10500.0),
            ("ticker_value_curve", "AAPL", 200.0),
            ("benchmark_curve", "benchmark_equity", 10200.0),
        ]:
            with self.subTest(curve=key):
                self.assertEqual(len(payload[key]), 2)
                self.assertEqual(payload[key][0]["date"], "2025-01-01T00:00:00.000")
                self.assertEqual(payload[key][1][column], expected)

    def test_details_handles_no_trades(self):
        self.results["trades"] = pd.DataFrame()
        response = self.client.post("/backtest?include_details=true", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trades"], [])

    def test_explicit_false_omits_details(self):
        response = self.client.post("/backtest?include_details=false", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"metrics"})

    def test_invalid_requests_fail_before_execution(self):
        cases = [
            {"unexpected": 1},
            {"initial_capital": "10000"},
            {"initial_capital": 0},
            {"tickers": []},
            {"tickers": ["AAPL"], "allocations": {"MSFT": 1}},
            {"start_date": "invalid"},
            {"strategy": "Unknown"},
            {"strategy_parameters": {"unknown": 1}},
            {"strategy_parameters": {"short_window": 0}},
            {"strategy_parameters": {"short_window": "10"}},
            {"strategy_parameters": {"short_window": True}},
            {"strategy": "RSI Reversion", "strategy_parameters": {"period": 1}},
            {"strategy": "RSI Reversion", "strategy_parameters": {"oversold": 90}},
            {"stop_loss_pct": 1},
            {"kelly_p": 0.5},
        ]
        for body in cases:
            with self.subTest(body=body):
                response = self.client.post("/backtest", json=body)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("detail", response.json())
        self.run.assert_not_called()

    def test_non_integer_rsi_period_returns_422_before_execution(self):
        for period in (2.5, 14.0):
            with self.subTest(period=period):
                response = self.client.post(
                    "/backtest",
                    json={"strategy": "RSI Reversion", "strategy_parameters": {"period": period}},
                )
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("integer", response.json()["detail"])
        self.run.assert_not_called()

    def test_invalid_query_and_missing_body_fail_before_execution(self):
        for response in [
            self.client.post("/backtest?include_details=invalid", json={}),
            self.client.post("/backtest"),
            self.client.post(
                "/backtest", content="{", headers={"Content-Type": "application/json"}
            ),
        ]:
            self.assertEqual(response.status_code, 422)
        self.run.assert_not_called()

    def test_backtest_requires_post(self):
        response = self.client.get("/backtest")
        self.assertEqual(response.status_code, 405)
        self.run.assert_not_called()
