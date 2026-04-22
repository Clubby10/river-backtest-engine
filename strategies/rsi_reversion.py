import pandas as pd

from strategies.base_strategy import BaseStrategy


class RSIReversion(BaseStrategy):
    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        if period < 2:
            raise ValueError("period must be >= 2")
        if not 0 <= oversold <= 100:
            raise ValueError("oversold must be between 0 and 100")
        if not 0 <= overbought <= 100:
            raise ValueError("overbought must be between 0 and 100")
        if oversold >= overbought:
            raise ValueError("oversold must be less than overbought")

        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def _compute_rsi(self, close: pd.Series) -> pd.Series:
        delta = close.diff()
        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)

        avg_gain = gains.ewm(alpha=1 / self.period, adjust=False, min_periods=self.period).mean()
        avg_loss = losses.ewm(alpha=1 / self.period, adjust=False, min_periods=self.period).mean()

        rs = avg_gain / avg_loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + rs))

        rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
        rsi = rsi.mask((avg_gain == 0) & (avg_loss > 0), 0.0)
        rsi = rsi.mask((avg_gain == 0) & (avg_loss == 0), 50.0)
        return rsi.fillna(50)

    def generate_signal(self, data: pd.DataFrame, current_index: int) -> int:
        if current_index < self.period:
            return 0

        close_window = data['Close'].iloc[:current_index + 1]
        current_rsi = float(self._compute_rsi(close_window).iloc[-1])

        if current_rsi <= self.oversold:
            return 1
        if current_rsi >= self.overbought:
            return -1
        return 0
