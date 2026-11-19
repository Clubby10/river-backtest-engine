"""Expose the backtest engine through FastAPI endpoints."""

import inspect
import json
from importlib import import_module
from pkgutil import iter_modules
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from . import strategies
from .config import CONFIG, BacktestConfig
from .service import build_strategy, run_backtest
from .strategies.base import BaseStrategy

app = FastAPI(title="River Backtest API")


class BacktestRequest(BaseModel):
    """Settings accepted by the backtest endpoint"""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
    )

    tickers: list[str] = Field(default_factory=lambda: list(CONFIG.tickers))
    allocations: dict[str, float] | None = None
    start_date: str = CONFIG.start_date
    initial_capital: float = CONFIG.initial_capital
    commission: float = CONFIG.commission
    slippage: float = CONFIG.slippage
    position_size: float = CONFIG.position_size

    strategy: str = CONFIG.strategy
    strategy_parameters: dict[str, int | float] = Field(default_factory=dict)

    kelly_p: float | None = CONFIG.kelly_p
    kelly_b: float | None = CONFIG.kelly_b
    use_rolling_kelly: bool = CONFIG.use_rolling_kelly
    kelly_lookback: int | None = CONFIG.kelly_lookback
    kelly_min_trades: int = CONFIG.kelly_min_trades

    stop_loss_pct: float | None = CONFIG.stop_loss_pct
    take_profit_pct: float | None = CONFIG.take_profit_pct
    max_drawdown_cutoff_pct: float | None = CONFIG.max_drawdown_cutoff_pct


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/strategies")
def get_strategies() -> Response:
    available: dict[str, dict[str, Any]] = {}

    for module_info in iter_modules(strategies.__path__, prefix=f"{strategies.__name__}."):
        module = import_module(module_info.name)

        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                not issubclass(cls, BaseStrategy)
                or inspect.isabstract(cls)
                or cls.__module__ != module.__name__
            ):
                continue

            if cls.name in available:
                raise ValueError(f"Duplicate strategy name: {cls.name}")

            available[cls.name] = {
                "name": cls.name,
                "description": cls.description,
                "default_parameters": cls.default_parameters,
            }

    result = {"strategies": [available[name] for name in sorted(available)]}

    return Response(content=json.dumps(result, indent=4), media_type="application/json")


def dataframe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(
        frame.to_json(
            orient="records",
            date_format="iso",
            double_precision=15,
        )
    )


@app.post("/backtest")
def backtest(request: BacktestRequest, include_details: bool = False) -> Response:
    """validate config and strategy parameters before downloading"""
    try:
        config = BacktestConfig(**request.model_dump()).validated()
        build_strategy(config)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    results = run_backtest(config)

    payload = {"metrics": dataframe_records(pd.DataFrame([results["metrics"]]))[0]}

    if include_details:  # long and spammy
        payload.update(
            {
                "trades": dataframe_records(results["trades"]),
                "equity_curve": dataframe_records(results["equity_curve"].reset_index()),
                "ticker_value_curve": dataframe_records(
                    results["ticker_value_curve"].reset_index()
                ),
                "benchmark_curve": dataframe_records(results["benchmark_curve"].reset_index()),
            }
        )

    return Response(
        content=json.dumps(payload, indent=4, allow_nan=False),
        media_type="application/json",
    )
