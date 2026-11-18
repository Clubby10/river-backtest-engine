"""Shared configuration, defaults, and validation for both interfaces."""

from dataclasses import dataclass, field, replace
from datetime import date
from math import isfinite
from typing import Optional

from .risk import kelly_criterion


def validate_engine_settings(
    initial_capital: float,
    commission: float,
    slippage: float,
    position_size: float,
    kelly_lookback: Optional[int],
    kelly_min_trades: int,
    stop_loss_pct: Optional[float],
    take_profit_pct: Optional[float],
    max_drawdown_cutoff_pct: Optional[float],
) -> None:
    """Validate simulation settings without loading prices or a GUI."""
    if not isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("initial_capital must be greater than zero")
    if not isfinite(commission) or commission < 0:
        raise ValueError("commission must be nonnegative")
    for name, value in (("slippage", slippage), ("position_size", position_size)):
        if not isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
    if not isinstance(kelly_min_trades, int) or kelly_min_trades < 1:
        raise ValueError("kelly_min_trades must be a positive integer")
    if kelly_lookback is not None and (not isinstance(kelly_lookback, int) or kelly_lookback < 1):
        raise ValueError("kelly_lookback must be a positive integer when provided")
    for name, value in (
        ("stop_loss_pct", stop_loss_pct),
        ("take_profit_pct", take_profit_pct),
        ("max_drawdown_cutoff_pct", max_drawdown_cutoff_pct),
    ):
        if value is not None and not 0 < value < 1:
            raise ValueError(f"{name} must be between 0 and 1")


def normalize_allocations(
    tickers: list[str], allocations: Optional[dict[str, float]]
) -> dict[str, float]:
    if allocations is None:
        return {ticker: 1.0 / len(tickers) for ticker in tickers}
    cleaned = {ticker.strip().upper(): float(weight) for ticker, weight in allocations.items()}
    if set(cleaned) != set(tickers):
        raise ValueError("Allocation tickers must match ticker list.")
    if any(not isfinite(weight) or weight < 0 for weight in cleaned.values()):
        raise ValueError("Allocations must be finite and nonnegative.")
    total = sum(cleaned.values())
    if not isfinite(total) or total <= 0:
        raise ValueError("Total allocation must be finite and greater than zero.")
    return {ticker: cleaned[ticker] / total for ticker in tickers}


@dataclass(frozen=True)
class BacktestConfig:
    tickers: list[str] = field(default_factory=lambda: ["AAPL", "MSFT", "NVDA"])
    allocations: Optional[dict[str, float]] = field(
        default_factory=lambda: {"AAPL": 0.34, "MSFT": 0.33, "NVDA": 0.33}
    )
    start_date: str = "2018-01-01"
    initial_capital: float = 10_000.0
    commission: float = 2.0
    slippage: float = 0.0001
    position_size: float = 0.50

    # Set both to None to disable static Kelly sizing.
    kelly_p: Optional[float] = None
    kelly_b: Optional[float] = None
    use_rolling_kelly: bool = True
    kelly_lookback: Optional[int] = 20
    kelly_min_trades: int = 10

    # Risk management exits. Set to None to disable.
    stop_loss_pct: Optional[float] = 0.25
    take_profit_pct: Optional[float] = 0.50
    max_drawdown_cutoff_pct: Optional[float] = 0.20

    strategy: str = "SMA Crossover"
    short_window: int = 20
    long_window: int = 50
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0

    def validated(self) -> "BacktestConfig":
        """Return a normalized copy, independent of the caller's portfolio containers."""
        tickers = list(dict.fromkeys(t.strip().upper() for t in self.tickers if t.strip()))
        if not tickers:
            raise ValueError("Please provide at least one ticker.")
        allocations = normalize_allocations(tickers, self.allocations)
        date.fromisoformat(self.start_date)
        validate_engine_settings(
            self.initial_capital,
            self.commission,
            self.slippage,
            self.position_size,
            self.kelly_lookback,
            self.kelly_min_trades,
            self.stop_loss_pct,
            self.take_profit_pct,
            self.max_drawdown_cutoff_pct,
        )
        if (self.kelly_p is None) != (self.kelly_b is None):
            raise ValueError("Provide both kelly_p and kelly_b, or leave both empty.")
        if self.kelly_p is not None:
            kelly_criterion(self.kelly_p, self.kelly_b)
        if self.strategy not in ("SMA Crossover", "RSI Reversion"):
            raise ValueError(f"Unknown strategy: {self.strategy}")
        return replace(self, tickers=tickers, allocations=allocations)


CONFIG = BacktestConfig()
# Preserve the desktop app's existing choice to leave the drawdown cutoff disabled.
GUI_CONFIG = replace(CONFIG, max_drawdown_cutoff_pct=None)
