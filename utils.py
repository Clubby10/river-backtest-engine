import matplotlib.pyplot as plt

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

def plot_equity_curve(equity_curve, ticker, initial_capital, ticker_value_curve=None) -> None:
    plt.figure(figsize=(12, 5))
    plt.plot(equity_curve['equity'], label='Portfolio equity', color='steelblue', linewidth=2)

    if ticker_value_curve is not None:
        for symbol in ticker_value_curve.columns:
            plt.plot(ticker_value_curve[symbol], label=f'{symbol} position value', alpha=0.8)

    plt.axhline(y=initial_capital, color='gray', linestyle='--', label='Initial capital')
    plt.title(f'Equity Curve — SMA Crossover on {ticker}')
    plt.xlabel('Date')
    plt.ylabel('Portfolio Value ($)')
    plt.legend()
    plt.tight_layout()
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
