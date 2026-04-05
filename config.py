from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BacktestConfig:
    ticker: str = "AAPL"
    start_date: str = "2018-01-01"
    initial_capital: float = 10_000.0
    commission: float = 2.0
    slippage: float = 0.0001
    position_size: float = 0.50

    # Set both to None to disable static Kelly sizing.
    kelly_p: Optional[float] = 0.88
    kelly_b: Optional[float] = 3.0

    use_rolling_kelly: bool = True
    kelly_lookback: Optional[int] = 20
    kelly_min_trades: int = 10

    short_window: int = 20
    long_window: int = 50


CONFIG = BacktestConfig()
