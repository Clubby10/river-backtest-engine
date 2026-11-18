"""Download adjusted daily prices from Yahoo Finance."""

import threading
from queue import Empty, Queue

import pandas as pd
import yfinance as yf


def download_prices(
    tickers: list[str], start_date: str, show_progress: bool
) -> dict[str, pd.DataFrame]:
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
