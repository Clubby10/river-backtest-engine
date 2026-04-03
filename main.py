import pandas as pd
import numpy as np

class BacktestEngine:
    def __init__(self, strategy, initial_capital: float = 10_000.0):
        self.strategy = strategy
        self.initial_capital = initial_capital

    def run(self, data: pd.DataFrame) -> dict:
        cash = self.initial_capital
        shares = 0
        in_market = False

        equity_curve = []
        trades = []

        for i in range(len(data)):
            price = float(data['Close'].iloc[i])
            date = data.index[i]

            signal = self.strategy.generate_signal(data, i)

            # execute trades
            # BUY
            if signal == 1 and not in_market:
                shares = int(cash // price)
                cash = cash - (shares * price)
                in_market = True
                trades.append({'date': date, 'action': 'BUY', 'price': price, 'shares': shares})
            # SELL
            elif signal == -1 and in_market:
                cash = cash + (shares * price)
                shares = 0
                in_market = False
                trades.append({'date': date, 'action': 'SELL', 'price': price, 'shares': shares})

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
