import pandas as pd
import numpy as np
from typing import Optional
from utils import kelly_criterion

class BacktestEngine:
    def __init__(self, strategy, initial_capital: float = 10_000.0, commission: float = 0, slippage: float = 0,
                 position_size: float = 1, kelly_position_size: Optional[float] = None,
                 use_rolling_kelly: bool = False, kelly_lookback: Optional[int] = None, kelly_min_trades: int = 10,
                 stop_loss_pct: Optional[float] = None, take_profit_pct: Optional[float] = None,
                 max_drawdown_cutoff_pct: Optional[float] = None, allocations: Optional[dict[str, float]] = None):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_size = kelly_position_size if kelly_position_size is not None else position_size
        self.use_rolling_kelly = use_rolling_kelly
        self.kelly_lookback = kelly_lookback
        self.kelly_min_trades = kelly_min_trades
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_drawdown_cutoff_pct = max_drawdown_cutoff_pct
        self.allocations = allocations

        if self.kelly_min_trades < 1:
            raise ValueError("kelly_min_trades must be >= 1")
        if self.kelly_lookback is not None and self.kelly_lookback < 1:
            raise ValueError("kelly_lookback must be >= 1 when provided")
        if self.stop_loss_pct is not None and not 0 < self.stop_loss_pct < 1:
            raise ValueError("stop_loss_pct must be between 0 and 1")
        if self.take_profit_pct is not None and not 0 < self.take_profit_pct < 1:
            raise ValueError("take_profit_pct must be between 0 and 1")
        if self.max_drawdown_cutoff_pct is not None and not 0 < self.max_drawdown_cutoff_pct < 1:
            raise ValueError("max_drawdown_cutoff_pct must be between 0 and 1")

    def _normalize_data(self, data: pd.DataFrame | dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        if isinstance(data, pd.DataFrame):
            return {"ASSET": data}
        if not isinstance(data, dict) or not data:
            raise ValueError("data must be a DataFrame or a non-empty dict[ticker, DataFrame]")
        for ticker, df in data.items():
            if not isinstance(df, pd.DataFrame):
                raise ValueError(f"data for ticker {ticker} must be a DataFrame")
        return data

    def _resolve_allocations(self, tickers: list[str]) -> dict[str, float]:
        if self.allocations is None:
            equal_weight = 1.0 / len(tickers)
            return {ticker: equal_weight for ticker in tickers}

        if set(self.allocations.keys()) != set(tickers):
            raise ValueError("allocations keys must match provided tickers")

        total_weight = sum(self.allocations.values())
        if total_weight <= 0 or total_weight > 1:
            raise ValueError("allocations must sum to > 0 and <= 1")

        for ticker, weight in self.allocations.items():
            if weight < 0:
                raise ValueError(f"allocation for {ticker} must be >= 0")

        return self.allocations

    def _estimate_rolling_kelly(self, closed_trade_returns: list[float]) -> Optional[float]:
        if len(closed_trade_returns) < self.kelly_min_trades:
            return None

        if self.kelly_lookback is None:
            sample = closed_trade_returns
        else:
            sample = closed_trade_returns[-self.kelly_lookback:]

        if len(sample) < self.kelly_min_trades:
            return None

        wins = [ret for ret in sample if ret > 0]
        losses = [-ret for ret in sample if ret < 0]
        if not wins or not losses:
            return None

        p = len(wins) / len(sample)
        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)

        if avg_loss <= 0:
            return None

        b = avg_win / avg_loss
        kelly_size = kelly_criterion(p, b)
        return kelly_size if kelly_size > 0 else None

    def run(self, data: pd.DataFrame | dict[str, pd.DataFrame]) -> dict:
        portfolio_data = self._normalize_data(data)
        tickers = list(portfolio_data.keys())
        allocations = self._resolve_allocations(tickers)

        cash = self.initial_capital
        positions = {ticker: 0 for ticker in tickers}
        open_trade_cost = {ticker: 0.0 for ticker in tickers}
        open_trade_share_cost = {ticker: 0.0 for ticker in tickers}
        closed_trade_returns = {ticker: [] for ticker in tickers}
        pending_signal = {ticker: 0 for ticker in tickers}
        price_cache = {ticker: 0.0 for ticker in tickers}
        peak_equity = self.initial_capital
        trading_halted = False

        all_dates = sorted(set().union(*[df.index.tolist() for df in portfolio_data.values()]))
        date_to_pos = {
            ticker: {dt: idx for idx, dt in enumerate(df.index)}
            for ticker, df in portfolio_data.items()
        }

        equity_curve = []
        ticker_value_curve = []
        trades = []

        for date in all_dates:
            for ticker in tickers:
                ticker_data = portfolio_data[ticker]
                if date not in date_to_pos[ticker]:
                    continue

                i = date_to_pos[ticker][date]
                close_price = float(ticker_data['Close'].iloc[i])
                price_cache[ticker] = close_price

                if not trading_halted and pending_signal[ticker] != 0:
                    execution_price = float(ticker_data['Open'].iloc[i])

                    if pending_signal[ticker] == 1 and cash > self.commission:
                        current_position_size = self.position_size
                        if self.use_rolling_kelly:
                            rolling_kelly = self._estimate_rolling_kelly(closed_trade_returns[ticker])
                            if rolling_kelly is not None:
                                current_position_size = rolling_kelly

                        execution_price = execution_price * (1 + self.slippage)
                        budget = cash * allocations[ticker] * current_position_size
                        new_shares = int(budget // execution_price)
                        if self.use_rolling_kelly and current_position_size > 0 and new_shares == 0:
                            min_trade_cash = execution_price + self.commission
                            if cash >= min_trade_cash:
                                new_shares = 1

                        if new_shares > 0:
                            trade_cost = (new_shares * execution_price) + self.commission
                            if trade_cost <= cash:
                                cash = cash - trade_cost
                                positions[ticker] += new_shares
                                open_trade_cost[ticker] += trade_cost
                                open_trade_share_cost[ticker] += new_shares * execution_price
                                trades.append({
                                    'date': date,
                                    'ticker': ticker,
                                    'action': 'BUY',
                                    'price': execution_price,
                                    'shares': positions[ticker]
                                })

                    elif pending_signal[ticker] == -1 and positions[ticker] > 0:
                        execution_price = execution_price * (1 - self.slippage)
                        sell_value = (positions[ticker] * execution_price) - self.commission
                        cash = cash + sell_value

                        if open_trade_cost[ticker] > 0:
                            trade_return = (sell_value - open_trade_cost[ticker]) / open_trade_cost[ticker]
                            closed_trade_returns[ticker].append(trade_return)

                        positions[ticker] = 0
                        open_trade_cost[ticker] = 0.0
                        open_trade_share_cost[ticker] = 0.0
                        trades.append({
                            'date': date,
                            'ticker': ticker,
                            'action': 'SELL',
                            'price': execution_price,
                            'shares': positions[ticker]
                        })

                if not trading_halted and positions[ticker] > 0 and open_trade_share_cost[ticker] > 0:
                    average_entry_price = open_trade_share_cost[ticker] / positions[ticker]
                    low_price = float(ticker_data['Low'].iloc[i])
                    high_price = float(ticker_data['High'].iloc[i])

                    stop_price = None
                    take_price = None
                    if self.stop_loss_pct is not None:
                        stop_price = average_entry_price * (1 - self.stop_loss_pct)
                    if self.take_profit_pct is not None:
                        take_price = average_entry_price * (1 + self.take_profit_pct)

                    exit_price = None
                    exit_action = None

                    if stop_price is not None and low_price <= stop_price:
                        exit_price = stop_price
                        exit_action = 'STOP_LOSS'
                    elif take_price is not None and high_price >= take_price:
                        exit_price = take_price
                        exit_action = 'TAKE_PROFIT'

                    if exit_price is not None:
                        execution_price = exit_price * (1 - self.slippage)
                        sell_value = (positions[ticker] * execution_price) - self.commission
                        cash = cash + sell_value

                        if open_trade_cost[ticker] > 0:
                            trade_return = (sell_value - open_trade_cost[ticker]) / open_trade_cost[ticker]
                            closed_trade_returns[ticker].append(trade_return)

                        positions[ticker] = 0
                        open_trade_cost[ticker] = 0.0
                        open_trade_share_cost[ticker] = 0.0
                        trades.append({
                            'date': date,
                            'ticker': ticker,
                            'action': exit_action,
                            'price': execution_price,
                            'shares': positions[ticker]
                        })

                if not trading_halted:
                    signal = self.strategy.generate_signal(ticker_data, i)
                    pending_signal[ticker] = signal if i + 1 < len(ticker_data) else 0
                else:
                    pending_signal[ticker] = 0

            portfolio_value = cash
            ticker_values = {'date': date}
            for ticker in tickers:
                ticker_market_value = positions[ticker] * price_cache[ticker]
                ticker_values[ticker] = ticker_market_value
                portfolio_value += ticker_market_value

            total_value = portfolio_value

            if total_value > peak_equity:
                peak_equity = total_value

            if not trading_halted and self.max_drawdown_cutoff_pct is not None and peak_equity > 0:
                drawdown_pct = (peak_equity - total_value) / peak_equity
                if drawdown_pct >= self.max_drawdown_cutoff_pct:
                    for ticker in tickers:
                        if positions[ticker] > 0 and price_cache[ticker] > 0:
                            execution_price = price_cache[ticker] * (1 - self.slippage)
                            sell_value = (positions[ticker] * execution_price) - self.commission
                            cash = cash + sell_value

                            if open_trade_cost[ticker] > 0:
                                trade_return = (sell_value - open_trade_cost[ticker]) / open_trade_cost[ticker]
                                closed_trade_returns[ticker].append(trade_return)

                            positions[ticker] = 0
                            open_trade_cost[ticker] = 0.0
                            open_trade_share_cost[ticker] = 0.0
                            trades.append({
                                'date': date,
                                'ticker': ticker,
                                'action': 'MAX_DRAWDOWN_EXIT',
                                'price': execution_price,
                                'shares': positions[ticker]
                            })

                    trading_halted = True
                    total_value = cash

            equity_curve.append({'date': date, 'equity': total_value})
            ticker_value_curve.append(ticker_values)

        equity_df = pd.DataFrame(equity_curve).set_index('date')
        ticker_value_df = pd.DataFrame(ticker_value_curve).set_index('date')

        metrics = self._compute_metrics(equity_df)

        return {
            'equity_curve': equity_df,
            'ticker_value_curve': ticker_value_df,
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
