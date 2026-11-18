"""Coordinate configuration, price loading, and backtest execution."""

from .config import BacktestConfig
from .data import download_prices
from .engine import BacktestEngine
from .risk import kelly_criterion
from .strategies.base import BaseStrategy
from .strategies.rsi_reversion import RSIReversion
from .strategies.sma_crossover import SMACrossover


def build_strategy(config: BacktestConfig) -> BaseStrategy:
    if config.strategy == "SMA Crossover":
        return SMACrossover(config.short_window, config.long_window)
    if config.strategy == "RSI Reversion":
        return RSIReversion(config.rsi_period, config.rsi_oversold, config.rsi_overbought)
    raise ValueError(f"Unknown strategy: {config.strategy}")


def run_backtest(config: BacktestConfig, *, show_download_progress: bool = False) -> dict:
    """Validate before network access; callers can also use the engine with offline data."""
    config = config.validated()
    strategy = build_strategy(config)
    kelly_size = (
        kelly_criterion(config.kelly_p, config.kelly_b) if config.kelly_p is not None else None
    )
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=config.initial_capital,
        commission=config.commission,
        slippage=config.slippage,
        position_size=config.position_size,
        kelly_position_size=kelly_size,
        use_rolling_kelly=config.use_rolling_kelly,
        kelly_lookback=config.kelly_lookback,
        kelly_min_trades=config.kelly_min_trades,
        stop_loss_pct=config.stop_loss_pct,
        take_profit_pct=config.take_profit_pct,
        max_drawdown_cutoff_pct=config.max_drawdown_cutoff_pct,
        allocations=config.allocations,
    )
    portfolio_data = download_prices(config.tickers, config.start_date, show_download_progress)
    return engine.run(portfolio_data)
