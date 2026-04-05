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
