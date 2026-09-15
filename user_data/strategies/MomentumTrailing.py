from freqtrade.strategy import IStrategy
from pandas import DataFrame


class MomentumTrailing(IStrategy):
    """
    Rule being tested:
    Enter when price rises ENTRY_PCT_THRESHOLD in the last candle.
    Exit on a pullback of trailing_stop_positive from the peak price
    reached during the trade (a trailing stop, not a fixed target).
    """

    INTERFACE_VERSION = 3
    timeframe = "1m"
    can_short = False
    startup_candle_count = 5

    # --- Exit logic: trailing stop only ---
    # Once a trade is trailing_stop_positive_offset in profit, freqtrade
    # starts trailing a stop trailing_stop_positive below the highest
    # price reached so far in the trade.
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.011
    trailing_only_offset_is_reached = True

    # Hard safety net in case price never reaches the offset above
    stoploss = -0.03

    # Disable freqtrade's separate ROI exit ladder - the trailing stop
    # above is the only exit rule for this strategy.
    minimal_roi = {"0": 10}

    # --- The parameter you'll change most often between test runs ---
    ENTRY_PCT_THRESHOLD = 0.01  # 1% rise in the last candle

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["pct_change_1m"] = dataframe["close"].pct_change(periods=1)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["pct_change_1m"] > self.ENTRY_PCT_THRESHOLD)
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No exit signal needed - the trailing stop above handles exits.
        return dataframe
