"""Expose the backtest engine through FastAPI endpoints."""

import inspect
import json

from importlib import import_module
from pkgutil import iter_modules
from typing import Any

from fastapi import FastAPI
from fastapi.responses import Response


from . import strategies
from .strategies.base import BaseStrategy

app = FastAPI(title="River Backtest API")

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

    result = { "strategies": [available[name] for name in sorted(available)] }

    return Response(content=json.dumps(result, indent=4), media_type="application/json")
