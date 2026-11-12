import threading
from collections import OrderedDict
from queue import Empty, Queue
from typing import Optional

import pandas as pd
import yfinance as yf

from main import BacktestEngine
from utils import kelly_criterion, validate


def _clean_tickers(tickers: list[str]) -> list[str]:
    cleaned = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
    unique = list(OrderedDict((ticker, None) for ticker in cleaned).keys())
    if not unique:
        raise ValueError("Please provide at least one ticker.")
    return unique


def _resolve_allocations(tickers: list[str], allocations: Optional[dict[str, float]]) -> dict[str, float]:
    if allocations is None:
        equal_weight = 1.0 / len(tickers)
        return {ticker: equal_weight for ticker in tickers}

    cleaned_allocations = {ticker.strip().upper(): float(weight) for ticker, weight in allocations.items()}

    if set(cleaned_allocations.keys()) != set(tickers):
        raise ValueError("Allocation tickers must match ticker list.")
    if any(weight < 0 for weight in cleaned_allocations.values()):
        raise ValueError("Allocations must be >= 0.")

    total_weight = sum(cleaned_allocations.values())
    if total_weight <= 0:
        raise ValueError("Total allocation must be greater than zero.")

    return {ticker: cleaned_allocations[ticker] / total_weight for ticker in tickers}


def _download_prices(tickers: list[str], start_date: str, show_progress: bool) -> dict[str, pd.DataFrame]:
    pending = Queue()
    completed = Queue()
    for ticker in tickers:
        pending.put(ticker)

    def worker():
        while True:
            try:
                ticker = pending.get_nowait()
            except Empty:
                return
            try:
                data = yf.Ticker(ticker).history(start=start_date, auto_adjust=True, actions=False)
                data = data.dropna(how="all")
                if data.empty:
                    raise ValueError(f"No data for ticker {ticker}")
                # Match the timezone-naive daily dates used by yf.download.
                data.index = data.index.tz_localize(None)
                completed.put((ticker, data))
            except Exception as exc:
                completed.put((ticker, exc))

    workers = [threading.Thread(target=worker) for _ in range(min(4, len(tickers)))]
    for thread in workers:
        thread.start()
    results = {}
    try:
        for count in range(1, len(tickers) + 1):
            ticker, result = completed.get()
            results[ticker] = result
            if show_progress:
                print(f"Processed {count}/{len(tickers)} tickers ({ticker})", flush=True)
    finally:
        for thread in workers:
            thread.join()

    portfolio_data = {}
    for ticker in tickers:
        result = results[ticker]
        if isinstance(result, Exception):
            raise result
        portfolio_data[ticker] = result
    return portfolio_data


def build_engine_and_data(
    *,
    strategy,
    tickers: list[str],
    start_date: str,
    initial_capital: float,
    commission: float,
    slippage: float,
    position_size: float,
    kelly_p: Optional[float] = None,
    kelly_b: Optional[float] = None,
    use_rolling_kelly: bool = False,
    kelly_lookback: Optional[int] = None,
    kelly_min_trades: int = 10,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    max_drawdown_cutoff_pct: Optional[float] = None,
    allocations: Optional[dict[str, float]] = None,
    show_download_progress: bool = False,
) -> tuple[BacktestEngine, dict[str, pd.DataFrame], list[str], dict[str, float]]:
    cleaned_tickers = _clean_tickers(tickers)
    resolved_allocations = _resolve_allocations(cleaned_tickers, allocations)

    if (kelly_p is None) ^ (kelly_b is None):
        raise ValueError("Provide both kelly_p and kelly_b, or leave both empty.")

    kelly_position_size = None
    if kelly_p is not None and kelly_b is not None:
        kelly_position_size = kelly_criterion(kelly_p, kelly_b)

    validate(initial_capital, commission, slippage, position_size)
    if kelly_position_size is not None:
        validate(initial_capital, commission, slippage, kelly_position_size)

    portfolio_data = _download_prices(cleaned_tickers, start_date, show_download_progress)

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
        allocations=resolved_allocations,
    )

    return engine, portfolio_data, cleaned_tickers, resolved_allocations
