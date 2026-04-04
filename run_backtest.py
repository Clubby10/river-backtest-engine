import yfinance as yf

from main import BacktestEngine
from strategies.sma_crossover import SMACrossover
from utils import print_results, plot_equity_curve, validate

ticker = 'AAPL'
initial_capital = 10000 # dollars           ( 1 - +inf )
commission = 2 # dollars 0+                 ( 0 - + inf )
slippage = 0.0001 # percentage 1% - 100%    ( 0.00 - 1 )
position_size = 0.80 # percentage 1% - 100% ( 0.00 - 1 )

validate(initial_capital, commission, slippage, position_size)

data = yf.download(ticker, start='2018-01-01', auto_adjust=True)
data.columns = data.columns.droplevel(1)

strategy = SMACrossover(short_window=20, long_window=50)
engine = BacktestEngine(strategy=strategy, initial_capital=initial_capital, commission=commission, slippage=slippage, position_size=position_size)
results = engine.run(data)

equity_curve = results['equity_curve']
trades = results['trades']
metrics = results['metrics']
metrics['num_trades'] = len(trades)

equity_curve = results['equity_curve']
trades = results['trades']
metrics = results['metrics']

metrics['num_trades'] = len(trades)

print_results(metrics, ticker)
plot_equity_curve(equity_curve, ticker, initial_capital)