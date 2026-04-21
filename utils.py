import matplotlib.pyplot as plt


def draw_backtest_chart(
    ax,
    equity_curve,
    ticker,
    ticker_value_curve=None,
    benchmark_curve=None,
    show_benchmark=False,
    normalize_benchmark=True,
):
    ax.clear()
    ax.set_facecolor("#1e293b")
    ax.plot(equity_curve.index, equity_curve["equity"], label="Portfolio Equity", color="#22d3ee", linewidth=2)

    if benchmark_curve is not None and show_benchmark:
        benchmark_series = benchmark_curve["benchmark_equity"]
        benchmark_label = "Benchmark"
        if normalize_benchmark and len(benchmark_series) > 0:
            benchmark_start = float(benchmark_series.iloc[0])
            equity_start = float(equity_curve["equity"].iloc[0])
            if benchmark_start != 0:
                benchmark_series = benchmark_series * (equity_start / benchmark_start)
                benchmark_label = "Benchmark (Normalized)"

        ax.plot(
            benchmark_curve.index,
            benchmark_series,
            label=benchmark_label,
            color="#f59e0b",
            linewidth=1.8,
            linestyle="--",
        )

    palette = ["#60a5fa", "#34d399", "#f472b6", "#c084fc", "#f97316", "#a3e635"]
    if ticker_value_curve is not None:
        for idx, symbol in enumerate(ticker_value_curve.columns):
            ax.plot(
                ticker_value_curve.index,
                ticker_value_curve[symbol],
                label=f"{symbol} Position Value",
                color=palette[idx % len(palette)],
                alpha=0.8,
                linewidth=1.4,
            )

    ax.set_title(f"Backtest: {ticker}", color="#f9fafb")
    ax.set_ylabel("Value ($)", color="#d1d5db")
    ax.tick_params(axis="x", colors="#d1d5db")
    ax.tick_params(axis="y", colors="#d1d5db")
    ax.grid(color="#334155", linestyle="--", linewidth=0.5, alpha=0.6)
    legend = ax.legend(facecolor="#1e293b", edgecolor="#334155", fontsize=8)
    for text in legend.get_texts():
        text.set_color("#e5e7eb")

def print_results(metrics, ticker) -> None:
    print(f"Backtest Results on {ticker}:")
    print(f"Total Return:   {metrics['total_return_pct']}%")
    print(f"Sharpe Ratio:   {metrics['sharpe_ratio']}")
    print(f"Max Drawdown:   {metrics['max_drawdown_pct']}%")
    if 'calmar_ratio' in metrics:
        print(f"Calmar Ratio:   {metrics['calmar_ratio']}")
    if 'win_rate_pct' in metrics:
        print(f"Win Rate:       {metrics['win_rate_pct']}%")
    if 'avg_win_pct' in metrics and 'avg_loss_pct' in metrics:
        print(f"Avg Win/Loss:   {metrics['avg_win_pct']}% / {metrics['avg_loss_pct']}%")
    if 'avg_win_loss_ratio' in metrics:
        print(f"Win/Loss Ratio: {metrics['avg_win_loss_ratio']}")
    if 'benchmark_return_pct' in metrics and 'outperformance_vs_benchmark_pct' in metrics:
        print(f"Benchmark Ret:  {metrics['benchmark_return_pct']}%")
        print(f"Vs Benchmark:   {metrics['outperformance_vs_benchmark_pct']}%")
    print(f"Num Trades:     {metrics['num_trades']}")

def plot_equity_curve(equity_curve, ticker, initial_capital, ticker_value_curve=None, metrics=None,
                      benchmark_curve=None, show_benchmark=False, normalize_benchmark=True) -> None:
    fig, ax = plt.subplots(figsize=(14, 7), dpi=100)
    fig.patch.set_facecolor("#0f172a")

    draw_backtest_chart(
        ax=ax,
        equity_curve=equity_curve,
        ticker=ticker,
        ticker_value_curve=ticker_value_curve,
        benchmark_curve=benchmark_curve,
        show_benchmark=show_benchmark,
        normalize_benchmark=normalize_benchmark,
    )

    if metrics is not None:
        stat_chunks = [
            f"Return: {metrics.get('total_return_pct', 0)}%",
            f"Sharpe: {metrics.get('sharpe_ratio', 0)}",
            f"MaxDD: {metrics.get('max_drawdown_pct', 0)}%",
            f"Calmar: {metrics.get('calmar_ratio', 0)}",
            f"Win Rate: {metrics.get('win_rate_pct', 0)}%",
            f"Trades: {metrics.get('num_trades', 0)}",
        ]
        if 'benchmark_return_pct' in metrics:
            stat_chunks.append(f"Benchmark: {metrics.get('benchmark_return_pct', 0)}%")

        fig.text(
            0.015,
            0.96,
            "  |  ".join(stat_chunks),
            color="#e5e7eb",
            fontsize=10,
            ha="left",
            va="top",
            bbox=dict(facecolor="#1e293b", edgecolor="#334155", boxstyle="round,pad=0.35"),
        )

    fig.subplots_adjust(top=0.88)
    plt.show()

def validate(initial_capital, commission, slippage, position_size) -> bool:
    if (initial_capital <= 0) or (commission < 0) or (slippage < 0 or slippage > 1) or (
            position_size < 0 or position_size > 1):
        raise ValueError("Invalid Inputs")
    return True

def kelly_criterion(p: float, b: float) -> float:
    if not 0 <= p <= 1:
        raise ValueError("p must be between 0 and 1")
    if b <= 0:
        raise ValueError("b must be greater than 0")

    q = 1 - p
    f = (b * p - q) / b
    return max(0.0, min(1.0, f))
