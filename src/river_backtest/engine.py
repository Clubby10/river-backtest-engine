"""Portfolio simulation with shared cash and next-bar execution."""

import threading
from concurrent.futures import Future
from typing import Optional

import pandas as pd

from .analytics import compute_benchmark_curve, compute_metrics
from .config import validate_engine_settings
from .risk import estimate_rolling_kelly


class BacktestEngine:
    def __init__(
        self,
        strategy,
        initial_capital: float = 10_000.0,
        commission: float = 0,
        slippage: float = 0,
        position_size: float = 1,
        kelly_position_size: Optional[float] = None,
        use_rolling_kelly: bool = False,
        kelly_lookback: Optional[int] = None,
        kelly_min_trades: int = 10,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        max_drawdown_cutoff_pct: Optional[float] = None,
        allocations: Optional[dict[str, float]] = None,
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_size = (
            kelly_position_size if kelly_position_size is not None else position_size
        )
        self.use_rolling_kelly = use_rolling_kelly
        self.kelly_lookback = kelly_lookback
        self.kelly_min_trades = kelly_min_trades
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_drawdown_cutoff_pct = max_drawdown_cutoff_pct
        self.allocations = allocations

        validate_engine_settings(
            initial_capital,
            commission,
            slippage,
            self.position_size,
            kelly_lookback,
            kelly_min_trades,
            stop_loss_pct,
            take_profit_pct,
            max_drawdown_cutoff_pct,
        )

    def _normalize_data(
        self, data: pd.DataFrame | dict[str, pd.DataFrame]
    ) -> dict[str, pd.DataFrame]:
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

    def _prepare_signals(self, portfolio_data):
        prepare = getattr(self.strategy, "prepare_signals", None)
        if prepare is None:
            return None
        if len(portfolio_data) == 1:
            return {ticker: prepare(data) for ticker, data in portfolio_data.items()}

        jobs = list(portfolio_data.items())
        futures = {ticker: Future() for ticker in portfolio_data}

        def worker(batch):
            for ticker, data in batch:
                try:
                    futures[ticker].set_result(prepare(data))
                except Exception as exc:
                    futures[ticker].set_exception(exc)

        worker_count = min(4, len(jobs))
        workers = [
            threading.Thread(target=worker, args=(jobs[i::worker_count],))
            for i in range(worker_count)
        ]
        for thread in workers:
            thread.start()
        for thread in workers:
            thread.join()
        return {ticker: future.result() for ticker, future in futures.items()}

    def run(self, data: pd.DataFrame | dict[str, pd.DataFrame]) -> dict:
        portfolio_data = self._normalize_data(data)
        tickers = list(portfolio_data.keys())
        allocations = self._resolve_allocations(tickers)

        all_dates = sorted(set().union(*(df.index for df in portfolio_data.values())))
        benchmark_result = Future()

        def compute_benchmark():
            try:
                curve = compute_benchmark_curve(
                    self.initial_capital, portfolio_data, all_dates, allocations
                )
                benchmark_result.set_result(curve)
            except BaseException as exc:
                benchmark_result.set_exception(exc)

        worker = threading.Thread(target=compute_benchmark, name="buy-and-hold-benchmark")
        worker.start()
        try:
            equity_df, ticker_value_df, trades, closed_trade_returns_all = self._simulate_trades(
                portfolio_data, tickers, allocations, all_dates
            )
        finally:
            worker.join()

        benchmark_curve = benchmark_result.result()
        metrics = compute_metrics(
            initial_capital=self.initial_capital,
            equity_df=equity_df,
            closed_trade_returns=closed_trade_returns_all,
            benchmark_equity=benchmark_curve["benchmark_equity"],
        )

        metrics["num_trades"] = len(trades)

        return {
            "equity_curve": equity_df,
            "ticker_value_curve": ticker_value_df,
            "benchmark_curve": benchmark_curve,
            "trades": pd.DataFrame(trades),
            "metrics": metrics,
        }

    def _simulate_trades(self, portfolio_data, tickers, allocations, all_dates):
        cash = self.initial_capital
        positions = {ticker: 0 for ticker in tickers}
        open_trade_cost = {ticker: 0.0 for ticker in tickers}
        open_trade_share_cost = {ticker: 0.0 for ticker in tickers}
        closed_trade_returns = {ticker: [] for ticker in tickers}
        pending_signal = {ticker: 0 for ticker in tickers}
        price_cache = {ticker: 0.0 for ticker in tickers}
        peak_equity = self.initial_capital
        trading_halted = False

        date_to_pos = {
            ticker: {dt: idx for idx, dt in enumerate(df.index)}
            for ticker, df in portfolio_data.items()
        }

        prepared_signals = self._prepare_signals(portfolio_data)
        equity_curve = []
        ticker_value_curve = []
        trades = []

        def close_position(ticker, date, price, action):
            """Record an exit before clearing its position and return net sale proceeds."""
            shares = positions[ticker]
            execution_price = price * (1 - self.slippage)
            proceeds = shares * execution_price - self.commission
            if open_trade_cost[ticker] > 0:
                trade_return = (proceeds - open_trade_cost[ticker]) / open_trade_cost[ticker]
                closed_trade_returns[ticker].append(trade_return)
            trades.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "action": action,
                    "price": execution_price,
                    "shares": shares,
                }
            )
            positions[ticker] = 0
            open_trade_cost[ticker] = 0.0
            open_trade_share_cost[ticker] = 0.0
            return proceeds

        for date in all_dates:
            for ticker in tickers:
                ticker_data = portfolio_data[ticker]
                if date not in date_to_pos[ticker]:
                    continue

                i = date_to_pos[ticker][date]
                close_price = float(ticker_data["Close"].iloc[i])
                price_cache[ticker] = close_price

                if not trading_halted and pending_signal[ticker] != 0:
                    execution_price = float(ticker_data["Open"].iloc[i])

                    if pending_signal[ticker] == 1 and cash > self.commission:
                        current_position_size = self.position_size
                        if self.use_rolling_kelly:
                            rolling_kelly = estimate_rolling_kelly(
                                closed_trade_returns[ticker],
                                self.kelly_min_trades,
                                self.kelly_lookback,
                            )
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
                                trades.append(
                                    {
                                        "date": date,
                                        "ticker": ticker,
                                        "action": "BUY",
                                        "price": execution_price,
                                        "shares": positions[ticker],
                                    }
                                )

                    elif pending_signal[ticker] == -1 and positions[ticker] > 0:
                        cash += close_position(ticker, date, execution_price, "SELL")

                if (
                    not trading_halted
                    and positions[ticker] > 0
                    and open_trade_share_cost[ticker] > 0
                ):
                    average_entry_price = open_trade_share_cost[ticker] / positions[ticker]
                    low_price = float(ticker_data["Low"].iloc[i])
                    high_price = float(ticker_data["High"].iloc[i])

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
                        exit_action = "STOP_LOSS"
                    elif take_price is not None and high_price >= take_price:
                        exit_price = take_price
                        exit_action = "TAKE_PROFIT"

                    if exit_price is not None:
                        cash += close_position(ticker, date, exit_price, exit_action)

                if not trading_halted:
                    if prepared_signals is None:
                        signal = self.strategy.generate_signal(ticker_data, i)
                    else:
                        signal = prepared_signals[ticker][i]
                    pending_signal[ticker] = signal if i + 1 < len(ticker_data) else 0
                else:
                    pending_signal[ticker] = 0

            portfolio_value = cash
            ticker_values = {"date": date}
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
                            cash += close_position(
                                ticker, date, price_cache[ticker], "MAX_DRAWDOWN_EXIT"
                            )

                    trading_halted = True
                    total_value = cash

            equity_curve.append({"date": date, "equity": total_value})
            ticker_value_curve.append(ticker_values)

        equity_df = pd.DataFrame(equity_curve).set_index("date")
        ticker_value_df = pd.DataFrame(ticker_value_curve).set_index("date")
        closed_trade_returns_all = [
            ret for ticker in tickers for ret in closed_trade_returns[ticker]
        ]

        return equity_df, ticker_value_df, trades, closed_trade_returns_all
