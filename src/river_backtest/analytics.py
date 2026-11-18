"""Portfolio benchmark and performance calculations."""

from typing import Optional

import numpy as np
import pandas as pd


def compute_benchmark_curve(
    initial_capital: float,
    portfolio_data: dict[str, pd.DataFrame],
    all_dates: list,
    allocations: dict[str, float],
) -> pd.DataFrame:
    benchmark_df = pd.DataFrame(index=pd.Index(all_dates, name="date"))

    for ticker, df in portfolio_data.items():
        close = df["Close"].astype(float)
        initial_close = float(close.iloc[0])
        alloc_capital = initial_capital * allocations[ticker]
        scaled = alloc_capital * (close / initial_close)
        aligned = scaled.reindex(benchmark_df.index).ffill().fillna(alloc_capital)
        benchmark_df[ticker] = aligned

    benchmark_df["benchmark_equity"] = benchmark_df.sum(axis=1)
    return benchmark_df


def compute_metrics(
    initial_capital: float,
    equity_df: pd.DataFrame,
    closed_trade_returns: list[float],
    benchmark_equity: Optional[pd.Series] = None,
) -> dict:
    equity = equity_df["equity"]

    total_return = (equity.iloc[-1] - initial_capital) / initial_capital * 100
    daily_returns = equity.pct_change().dropna()

    sharpe = (
        (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        if daily_returns.std() != 0
        else 0.0
    )

    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_drawdown = drawdown.min() * 100

    calmar = total_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

    wins = [ret for ret in closed_trade_returns if ret > 0]
    losses = [ret for ret in closed_trade_returns if ret < 0]
    win_rate = (len(wins) / len(closed_trade_returns) * 100) if closed_trade_returns else 0.0
    avg_win = (sum(wins) / len(wins) * 100) if wins else 0.0
    avg_loss = (sum(losses) / len(losses) * 100) if losses else 0.0
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

    benchmark_return = 0.0
    benchmark_outperformance = 0.0
    if benchmark_equity is not None and len(benchmark_equity) > 0:
        benchmark_return = (
            (benchmark_equity.iloc[-1] - benchmark_equity.iloc[0]) / benchmark_equity.iloc[0] * 100
        )
        benchmark_outperformance = total_return - benchmark_return

    return {
        "total_return_pct": round(total_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "calmar_ratio": round(calmar, 2),
        "win_rate_pct": round(win_rate, 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "avg_win_loss_ratio": round(win_loss_ratio, 2),
        "benchmark_return_pct": round(benchmark_return, 2),
        "outperformance_vs_benchmark_pct": round(benchmark_outperformance, 2),
    }
