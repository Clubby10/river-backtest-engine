import yfinance as yf

from main import BacktestEngine
from strategies.sma_crossover import SMACrossover
from utils import print_results, plot_equity_curve, validate, kelly_criterion

ticker = 'AAPL'
initial_capital = 10000 # dollars           ( 1 - +inf )
commission = 2 # dollars 0+                 ( 0 - + inf )
slippage = 0.0001 # percentage 1% - 100%    ( 0.00 - 1 )
position_size = 0.50 # percentage 1% - 100% ( 0.00 - 1 )
kelly_p = 0.88 # win probability for Kelly ( 0.00 - 1 ) NONE TO USE NORMAL POSITION SIZE
kelly_b = 3 # win/loss payoff ratio (> 0)            NONE TO USE NORMAL POSITION SIZE
use_rolling_kelly = True
kelly_lookback = 20
kelly_min_trades = 10

kelly_position_size = None
if kelly_p is not None and kelly_b is not None:
    kelly_position_size = kelly_criterion(kelly_p, kelly_b)

validate(initial_capital, commission, slippage, position_size)
if kelly_position_size is not None:
    validate(initial_capital, commission, slippage, kelly_position_size)

data = yf.download(ticker, start='2018-01-01', auto_adjust=True)
data.columns = data.columns.droplevel(1)

strategy = SMACrossover(short_window=20, long_window=50)
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
)
results = engine.run(data)

equity_curve = results['equity_curve']
trades = results['trades']
metrics = results['metrics']
metrics['num_trades'] = len(trades)

print_results(metrics, ticker)
plot_equity_curve(equity_curve, ticker, initial_capital)
