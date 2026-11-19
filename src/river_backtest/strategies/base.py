from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pandas as pd


class BaseStrategy(ABC):
    """Signal interface; strategies may also implement prepare_signals(data).

    Prepared signals must match generate_signal at each positional index and
    depend only on prices available through that index. The engine may prepare
    different tickers concurrently, so implementations must not share mutable state.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    default_parameters: ClassVar[dict[str, Any]]

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame, current_index: int) -> int:
        """
        Gets called by the engine on every trading day

        Parameters:
            data - full price history DataFrame
            current_index - the positional index of today in the DataFrame

        Returns:
            1 = BUY
            0 = HOLD
            -1 = SELL
        """
        pass
