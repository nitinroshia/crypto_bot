from freqtrade.strategy import IStrategy
from pandas import DataFrame


class MomentumTrailing(IStrategy):
    """
    Rule being tested:
    Enter when price rises more than the entry threshold in the last candle.
    Exit on a pullback of trailing_stop_positive from the peak price
    reached during the trade (a trailing stop, not a fixed target).

    Parameter consolidation: every value you'd change between test runs --
    timeframe, stoploss, the trailing-stop numbers, and the entry threshold
    below -- now lives in ONE place: whichever --config file you layer on
    top of config.json (see user_data/test_params.json and backtest.sh).
    Nothing in this file needs editing to test a different timeframe or
    threshold.

    How this works, for anyone extending it: timeframe/stoploss/trailing_stop*
    /minimal_roi are all attributes freqtrade's own StrategyResolver already
    knows how to override from a config file (this is the same mechanism
    that already overrides `timeframe` -- confirmed working via
    "Override strategy 'timeframe' with value from the configuration" in the
    bot's own log output). ENTRY_PCT_THRESHOLD is NOT one of freqtrade's
    known attributes, so it's read explicitly from self.config (a plain
    dict freqtrade populates with the fully merged configuration,
    documented in freqtrade's own advanced-strategy examples) with the
    class attribute below kept only as the fallback default.
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

    # Fallback only -- overridden by "entry_pct_threshold" in whatever
    # --config file you pass after config.json (see test_params.json).
    ENTRY_PCT_THRESHOLD = 0.01

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["pct_change_1m"] = dataframe["close"].pct_change(periods=1)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        threshold = self.config.get("entry_pct_threshold", self.ENTRY_PCT_THRESHOLD)
        dataframe.loc[
            (dataframe["pct_change_1m"] > threshold)
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No exit signal needed - the trailing stop above handles exits.
        return dataframe