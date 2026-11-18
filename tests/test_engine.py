import unittest

import pandas as pd

from river_backtest.engine import BacktestEngine


def prices(opens, closes=None, lows=None, highs=None, dates=None):
    closes = opens if closes is None else closes
    return pd.DataFrame(
        {
            "Open": opens,
            "Close": closes,
            "Low": closes if lows is None else lows,
            "High": closes if highs is None else highs,
        },
        index=pd.date_range("2024-01-01", periods=len(opens)) if dates is None else dates,
    )


class FixedSignals:
    def __init__(self, signals):
        self.signals = signals

    def generate_signal(self, data, current_index):
        return self.signals[current_index]


class EngineTests(unittest.TestCase):
    def test_signals_execute_at_next_open_with_costs(self):
        result = BacktestEngine(
            FixedSignals([1, -1, 1]),
            initial_capital=1000,
            commission=2,
            slippage=0.01,
            position_size=0.5,
        ).run(prices([10, 10, 12], closes=[10, 11, 12]))
        trades = result["trades"]
        self.assertEqual(trades["action"].tolist(), ["BUY", "SELL"])
        self.assertEqual(trades["date"].tolist(), list(pd.date_range("2024-01-02", periods=2)))
        self.assertEqual(trades["shares"].tolist(), [49, 49])
        self.assertAlmostEqual(trades.iloc[0]["price"], 10.1)
        self.assertAlmostEqual(trades.iloc[1]["price"], 11.88)
        self.assertAlmostEqual(result["equity_curve"].iloc[-1]["equity"], 1083.22)
        self.assertEqual(result["metrics"]["num_trades"], 2)

    def test_all_risk_exits_record_quantity_and_net_proceeds(self):
        cases = [
            ("STOP_LOSS", {"stop_loss_pct": 0.1}, [10, 10, 10], [10, 8, 10], [10, 10, 10], 9),
            ("TAKE_PROFIT", {"take_profit_pct": 0.1}, [10, 10, 10], [10, 10, 10], [10, 12, 10], 11),
            (
                "MAX_DRAWDOWN_EXIT",
                {"max_drawdown_cutoff_pct": 0.1},
                [10, 7, 7],
                [10, 7, 7],
                [10, 10, 7],
                7,
            ),
        ]
        for action, settings, closes, lows, highs, exit_price in cases:
            with self.subTest(action=action):
                result = BacktestEngine(
                    FixedSignals([1, 0, 0]),
                    initial_capital=1000,
                    position_size=0.5,
                    commission=2,
                    slippage=0.01,
                    **settings,
                ).run(prices([10, 10, 10], closes, lows, highs))
                sold = result["trades"].iloc[1]
                self.assertEqual(sold["action"], action)
                self.assertEqual(sold["shares"], 49)
                # Stop/take levels are based on the entry price including slippage.
                expected_price = exit_price * (1.01 if action != "MAX_DRAWDOWN_EXIT" else 1) * 0.99
                self.assertAlmostEqual(sold["price"], expected_price)
                self.assertAlmostEqual(
                    result["equity_curve"].iloc[-1]["equity"],
                    1000 - (49 * 10.1 + 2) + (49 * expected_price - 2),
                )

    def test_missing_dates_wait_for_tickers_next_available_open(self):
        data = {
            "AAA": prices([10, 12], dates=pd.to_datetime(["2024-01-01", "2024-01-03"])),
            "BBB": prices([20, 21, 22]),
        }
        result = BacktestEngine(FixedSignals([1, 0, 0]), initial_capital=1000).run(data)
        trades = result["trades"].set_index("ticker")
        self.assertEqual(trades.loc["AAA", "date"], pd.Timestamp("2024-01-03"))
        self.assertEqual(trades.loc["BBB", "date"], pd.Timestamp("2024-01-02"))
        self.assertEqual(result["benchmark_curve"]["benchmark_equity"].tolist(), [1000, 1025, 1150])

    def test_drawdown_halts_subsequent_buys(self):
        result = BacktestEngine(
            FixedSignals([1, 1, 1, 1]),
            initial_capital=1000,
            position_size=0.5,
            max_drawdown_cutoff_pct=0.1,
        ).run(prices([10, 10, 10, 10], closes=[10, 7, 10, 10]))
        self.assertEqual(result["trades"]["action"].tolist(), ["BUY", "MAX_DRAWDOWN_EXIT"])
        self.assertEqual(result["equity_curve"]["equity"].tolist(), [1000, 850, 850, 850])

    def test_no_trades_leaves_cash_unchanged(self):
        result = BacktestEngine(FixedSignals([0, 0, 0]), initial_capital=1000).run(
            prices([10, 11, 12])
        )
        self.assertTrue(result["trades"].empty)
        self.assertEqual(result["equity_curve"]["equity"].tolist(), [1000, 1000, 1000])
        self.assertEqual(result["metrics"]["num_trades"], 0)
