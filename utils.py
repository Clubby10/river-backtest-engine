import matplotlib.pyplot as plt

def print_results(metrics, ticker):
    print(f"Backtest Results on {ticker}:")
    print(f"Total Return:   {metrics['total_return_pct']}%")
    print(f"Sharpe Ratio:   {metrics['sharpe_ratio']}")
    print(f"Max Drawdown:   {metrics['max_drawdown_pct']}%")
    print(f"Num Trades:     {metrics['num_trades']}")

def plot_equity_curve(equity_curve, ticker, initial_capital):
    plt.figure(figsize=(12, 5))
    plt.plot(equity_curve['equity'], label='Strategy equity', color='steelblue')
    plt.axhline(y=initial_capital, color='gray', linestyle='--', label='Initial capital')
    plt.title(f'Equity Curve — SMA Crossover on {ticker}')
    plt.xlabel('Date')
    plt.ylabel('Portfolio Value ($)')
    plt.legend()
    plt.tight_layout()
    plt.show()

def validate(initial_capital, commission, slippage, position_size):
    if (initial_capital <= 0) or (commission < 0) or (slippage < 0 or slippage > 1) or (
            position_size < 0 or position_size > 1):
        raise ValueError("Invalid Inputs")
    return True