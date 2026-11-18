"""Command-line entry point."""

from .config import CONFIG
from .service import run_backtest


def main() -> None:
    from .reporting import plot_equity_curve, print_results

    config = CONFIG.validated()
    results = run_backtest(config, show_download_progress=True)
    label = ",".join(config.tickers)
    print_results(results["metrics"], label)
    plot_equity_curve(
        results["equity_curve"],
        label,
        ticker_value_curve=results["ticker_value_curve"],
        metrics=results["metrics"],
        benchmark_curve=results["benchmark_curve"],
        show_benchmark=False,
        normalize_benchmark=True,
    )


if __name__ == "__main__":
    main()
