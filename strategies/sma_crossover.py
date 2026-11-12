import numpy as np
import pandas as pd
from strategies.base_strategy import BaseStrategy

class SMACrossover(BaseStrategy):
    """
    BUY when short SMA crossed above long SMA,
    SELL when it crosses below,
    HOLD otherwise.
    https://www.researchgate.net/publication/370888513_Simple_Moving_Average_SMA_Crossover_Strategy_with_Buy_Sell_Indicator
    """
    def __init__(self, short_window: int = 10, long_window: int = 50):
        self.short_window = short_window
        self.long_window = long_window

    def prepare_signals(self, data: pd.DataFrame):
        if self.short_window <= 0 or self.long_window <= 0:
            return [self.generate_signal(data, i) for i in range(len(data))]

        close = data["Close"]
        short = close.rolling(self.short_window, min_periods=1).mean()
        long = close.rolling(self.long_window, min_periods=1).mean()
        buy = (short.shift() <= long.shift()) & (short > long)
        sell = (short.shift() >= long.shift()) & (short < long)
        signals = buy.astype("int8") - sell.astype("int8")

        # Rolling and slice means can round differently at a crossover boundary.
        near_tie = np.isclose(short, long, rtol=1e-13, atol=1e-15)
        for i in np.flatnonzero(near_tie[:-1] | near_tie[1:]) + 1:
            if i >= self.long_window:
                signals.iloc[i] = self.generate_signal(data, i)
        signals.iloc[:self.long_window] = 0
        return signals.to_numpy()

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> int:
        if current_index < self.long_window:
            return 0 # not enough data

        window = data['Close'].iloc[:current_index + 1]

        short_sma = window.iloc[-self.short_window:].mean()
        long_sma = window.iloc[-self.long_window:].mean()

        prev_window = data['Close'].iloc[:current_index]
        prev_short = prev_window.iloc[-self.short_window:].mean()
        prev_long = prev_window.iloc[-self.long_window:].mean()

        # crossover up
        if prev_short <= prev_long and short_sma > long_sma:
            return 1 # BUY

        # crossover down
        if prev_short >= prev_long and short_sma < long_sma:
            return -1 # SELL

        return 0 # HOLD
