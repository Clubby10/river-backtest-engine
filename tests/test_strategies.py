import unittest

import numpy as np
import pandas as pd

from river_backtest.risk import estimate_rolling_kelly
from river_backtest.strategies.rsi_reversion import RSIReversion
from river_backtest.strategies.sma_crossover import SMACrossover


class StrategyTests(unittest.TestCase):
    def test_prepared_signals_match_incremental_signals(self):
        rng = np.random.default_rng(19)
        paths = [np.full(100, 100.0), np.arange(1, 101), 100 + rng.normal(size=100).cumsum()]
        for strategy in [SMACrossover(5, 15), RSIReversion()]:
            for path in paths:
                with self.subTest(strategy=type(strategy).__name__, path_start=path[0]):
                    data = pd.DataFrame({"Close": path})
                    expected = [strategy.generate_signal(data, i) for i in range(len(data))]
                    np.testing.assert_array_equal(strategy.prepare_signals(data), expected)

    def test_future_prices_do_not_change_prepared_past_signals(self):
        data = pd.DataFrame({"Close": 100 + np.sin(np.arange(100)) * 10})
        for strategy in [SMACrossover(5, 15), RSIReversion()]:
            with self.subTest(strategy=type(strategy).__name__):
                np.testing.assert_array_equal(
                    strategy.prepare_signals(data)[:60], strategy.prepare_signals(data.iloc[:60])
                )

    def test_rolling_kelly_uses_only_requested_sample(self):
        self.assertIsNone(estimate_rolling_kelly([0.1], min_trades=2, lookback=None))
        self.assertIsNone(estimate_rolling_kelly([0.1, 0.2], min_trades=2, lookback=None))
        self.assertAlmostEqual(
            estimate_rolling_kelly([-1, 0.2, 0.1, -0.1], min_trades=3, lookback=3), 4 / 9
        )
