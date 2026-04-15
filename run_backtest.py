import yfinance as yf

from config import CONFIG
from main import BacktestEngine
from strategies.sma_crossover import SMACrossover
from utils import print_results, plot_equity_curve, validate, kelly_criterion

ticker = CONFIG.ticker
initial_capital = CONFIG.initial_capital
commission = CONFIG.commission
slippage = CONFIG.slippage
position_size = CONFIG.position_size
kelly_p = CONFIG.kelly_p
kelly_b = CONFIG.kelly_b
use_rolling_kelly = CONFIG.use_rolling_kelly
kelly_lookback = CONFIG.kelly_lookback
kelly_min_trades = CONFIG.kelly_min_trades
stop_loss_pct = CONFIG.stop_loss_pct
take_profit_pct = CONFIG.take_profit_pct
max_drawdown_cutoff_pct = CONFIG.max_drawdown_cutoff_pct

kelly_position_size = None
if kelly_p is not None and kelly_b is not None:
    kelly_position_size = kelly_criterion(kelly_p, kelly_b)

validate(initial_capital, commission, slippage, position_size)
if kelly_position_size is not None:
    validate(initial_capital, commission, slippage, kelly_position_size)

data = yf.download(ticker, start=CONFIG.start_date, auto_adjust=True)
data.columns = data.columns.droplevel(1)

strategy = SMACrossover(short_window=CONFIG.short_window, long_window=CONFIG.long_window)
engine = BacktestEngine(
    strategy=strategy,
    initial_capital=initial_capital,
    commission=commission,
    slippage=slippage,
    position_size=position_size,
    kelly_position_size=kelly_position_size,
    use_rolling_kelly=use_rolling_kelly,
    kelly_lookback=kelly_lookback,
    kelly_min_trades=kelly_min_trades,
    stop_loss_pct=stop_loss_pct,
    take_profit_pct=take_profit_pct,
    max_drawdown_cutoff_pct=max_drawdown_cutoff_pct,
)
results = engine.run(data)

equity_curve = results['equity_curve']
trades = results['trades']
metrics = results['metrics']
metrics['num_trades'] = len(trades)

print_results(metrics, ticker)
plot_equity_curve(equity_curve, ticker, initial_capital)
