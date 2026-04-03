from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    #Every strategy must inherit this class and implement a generate_signal()
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame, current_index: int) -> int:
        """
        Gets called by the engine on every trading day

        Parameters:
            data - fill price history data frame
            index - the index of today in the DataFrame

        Returns:
            1 = BUY
            0 = HOLD
            -1 = SELL
        """
        pass