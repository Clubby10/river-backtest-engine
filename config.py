from dataclasses import dataclass, field
from typing import Optional


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

    short_window: int = 20
    long_window: int = 50


CONFIG = BacktestConfig()
