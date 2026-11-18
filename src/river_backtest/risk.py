"""Static and rolling Kelly position sizing."""

from math import isfinite
from typing import Optional


def kelly_criterion(p: float, b: float) -> float:
    if not 0 <= p <= 1:
        raise ValueError("p must be between 0 and 1")
    if not isfinite(b) or b <= 0:
        raise ValueError("b must be finite and greater than 0")

    q = 1 - p
    f = (b * p - q) / b
    return max(0.0, min(1.0, f))


def estimate_rolling_kelly(
    closed_trade_returns: list[float], min_trades: int, lookback: Optional[int]
) -> Optional[float]:
    if len(closed_trade_returns) < min_trades:
        return None

    if lookback is None:
        sample = closed_trade_returns
    else:
        sample = closed_trade_returns[-lookback:]

    if len(sample) < min_trades:
        return None

    wins = [ret for ret in sample if ret > 0]
    losses = [-ret for ret in sample if ret < 0]
    if not wins or not losses:
        return None

    p = len(wins) / len(sample)
    avg_win = sum(wins) / len(wins)
    avg_loss = sum(losses) / len(losses)

    if avg_loss <= 0:
        return None

    b = avg_win / avg_loss
    kelly_size = kelly_criterion(p, b)
    return kelly_size if kelly_size > 0 else None
