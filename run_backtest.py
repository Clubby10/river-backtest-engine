import yfinance as yf

from main import BacktestEngine
from strategies.sma_crossover import SMACrossover
from utils import print_results, plot_equity_curve

ticker = 'AAPL'
initial_capital = 1000
commission = 2
slippage = 0.0001

data = yf.download(ticker, start='2018-01-01', auto_adjust=True)
data.columns = data.columns.droplevel(1)

strategy = SMACrossover(short_window=20, long_window=50)
engine = BacktestEngine(strategy=strategy, initial_capital=initial_capital, commission=commission, slippage=slippage)
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




