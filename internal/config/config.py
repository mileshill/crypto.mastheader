"""
config.py
config loads all env vars
"""
import os


class HarvestConfig:
    def __init__(self):
        self.kucoin_url_alltickers = os.getenv("KUCOIN_URL_ALLTICKERS", None)
        self.santiment_key = os.getenv("SANTIMENT_KEY", None)
        self.table_discovery = os.getenv("TABLE_DISCOVERY", None)
        self.table_harvest = os.getenv("TABLE_HARVEST", None)
        # self.table_strategy_meta = os.getenv("TABLE_STRATEGY_META", None)
        self.table_strategy_details = os.getenv("TABLE_STRATEGY_DETAILS", None)
        self.table_account = os.getenv("TABLE_ACCOUNT", None)
        self.table_account_log = os.getenv("TABLE_ACCOUNT_LOG", None)
        # self.table_trade_meta = os.getenv("TABLE_TRADE_META", None)
        # self.table_trade_details = os.getenv("TABLE_TRADE_DETAILS", None)
        self.table_orders = os.getenv("TABLE_ORDERS", None)
        self.queue_harvest = os.getenv("QUEUE_HARVEST", None)
        self.queue_strategy = os.getenv("QUEUE_STRATEGY", None)
        #self.queue_trade = os.getenv("QUEUE_TRADE", None)
        self.queue_trade_buy = os.getenv("QUEUE_TRADE_BUY", None)
        self.queue_trade_sell = os.getenv("QUEUE_TRADE_SELL", None)
        self.queue_monitor = os.getenv("QUEUE_MONITOR", None)
        self.sns_topic_discovery = os.getenv("SNS_TOPIC_DISCOVERY", None)
        self.sns_topic_strategy = os.getenv("SNS_TOPIC_STRATEGY", None)
        self.ses_sender = os.getenv("SES_SENDER", None)
        self.ses_recipient = os.getenv("SES_RECIPIENT", None)
        self.time_format = "%Y-%m-%dT%H:%M:%SZ"
        self.env = os.getenv("ENV", None)

        # Kucoin
        self.kucoin_key = os.getenv("KUCOIN_KEY", None)
        self.kucoin_secret = os.getenv("KUCOIN_SECRET", None)
        self.kucoin_api_passphrase = os.getenv("KUCOIN_API_PASSPHRASE", None)

        # Strategy Data
        self.strategy_daa_enter = os.getenv("STRATEGY_DAA_ENTER", None)
        self.strategy_daa_exit = os.getenv("STRATEGY_DAA_EXIT", None)
        self.strategy_sma_lookback = os.getenv("STRATEGY_SMA_LOOKBACK", None)
        self.strategy_volatility_enter = os.getenv("STRATEGY_VOLATILITY_ENTER", None)
        self.strategy_volatility_exit = os.getenv("STRATEGY_VOLATILITY_EXIT", None)
        self.strategy_max_trades = os.getenv("STRATEGY_MAX_TRADES", None)
        self.validate()

    def validate(self):
        """
        Loads relevant env vars and assigns to self. Ensures vars are populated and not None
        :return:
        """
        for k, v in self.__dict__.items():
            if k.startswith("strategy") and v is not None:
                self.__dict__[k] = float(v)
            if v is None:
                raise Exception(f"Missing env var - key {k} value {v}")
