from backtest_builder import build_engine_and_data
from config import CONFIG
from strategies.sma_crossover import SMACrossover
from utils import print_results, plot_equity_curve

strategy = SMACrossover(short_window=CONFIG.short_window, long_window=CONFIG.long_window)
engine, portfolio_data, tickers, _ = build_engine_and_data(
    strategy=strategy,
    tickers=CONFIG.tickers,
    start_date=CONFIG.start_date,
    initial_capital=CONFIG.initial_capital,
    commission=CONFIG.commission,
    slippage=CONFIG.slippage,
    position_size=CONFIG.position_size,
    kelly_p=CONFIG.kelly_p,
    kelly_b=CONFIG.kelly_b,
    use_rolling_kelly=CONFIG.use_rolling_kelly,
    kelly_lookback=CONFIG.kelly_lookback,
    kelly_min_trades=CONFIG.kelly_min_trades,
    stop_loss_pct=CONFIG.stop_loss_pct,
    take_profit_pct=CONFIG.take_profit_pct,
    max_drawdown_cutoff_pct=CONFIG.max_drawdown_cutoff_pct,
    allocations=CONFIG.allocations,
    show_download_progress=True,
)
results = engine.run(portfolio_data)

equity_curve = results['equity_curve']
ticker_value_curve = results['ticker_value_curve']
benchmark_curve = results.get('benchmark_curve')
trades = results['trades']
metrics = results['metrics']
metrics['num_trades'] = len(trades)

label = ",".join(tickers)
print_results(metrics, label)
plot_equity_curve(
    equity_curve,
    label,
    CONFIG.initial_capital,
    ticker_value_curve=ticker_value_curve,
    metrics=metrics,
    benchmark_curve=benchmark_curve,
    show_benchmark=False,
    normalize_benchmark=True,
)
