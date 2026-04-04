import pandas as pd
import numpy as np

class BacktestEngine:
    def __init__(self, strategy, initial_capital: float = 10_000.0, commission: float = 0, slippage: float = 0, position_size: float = 1):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_size = position_size

    def run(self, data: pd.DataFrame) -> dict:
        cash = self.initial_capital
        shares = 0

        equity_curve = []
        trades = []

        for i in range(len(data)):
            price = float(data['Close'].iloc[i]) # using CLOSE to generate the signal
            date = data.index[i]

            signal = self.strategy.generate_signal(data, i)

            execution_price = price
            execution_date = date

            # execute trades
            if signal != 0 and i + 1 < len(data):
                execution_price = float(data['Open'].iloc[i + 1]) # executing the trade the next day OPEN based on the close signal
                execution_date = data.index[i + 1]
            # BUY
            if signal == 1 and cash > self.commission:
                execution_price = execution_price * (1 + self.slippage)
                new_shares = int(((cash * self.position_size)) // execution_price)
                if new_shares > 0:
                    cash = cash - (new_shares * execution_price) - self.commission
                    shares += new_shares
                    trades.append({'date': execution_date, 'action': 'BUY', 'price': execution_price, 'shares': shares})
            # SELL
            elif signal == -1 and shares > 0:
                execution_price = execution_price * (1 - self.slippage)
                cash = (cash + (shares * execution_price)) - self.commission
                shares = 0
                trades.append({'date': execution_date, 'action': 'SELL', 'price': execution_price, 'shares': shares})

            total_value = cash + (shares * price)
            equity_curve.append({'date': date, 'equity': total_value})

        equity_df = pd.DataFrame(equity_curve).set_index('date')

        metrics = self._compute_metrics(equity_df)

        return {
            'equity_curve': equity_df,
            'trades': pd.DataFrame(trades),
            'metrics': metrics
        }

    def _compute_metrics(self, equity_df: pd.DataFrame) -> dict:
        equity = equity_df['equity']

        total_return = (equity.iloc[-1] - self.initial_capital) / self.initial_capital * 100
        daily_returns = equity.pct_change().dropna()

        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) \
            if daily_returns.std() != 0 else 0.0

        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100

        return {
            'total_return_pct': round(total_return, 2),
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'num_trades': 0
        }
