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
        self.table_trade = os.getenv("TABLE_STRATEGY", None)
        self.queue_harvest = os.getenv("QUEUE_HARVEST", None)
        self.queue_trade = os.getenv("QUEUE_STRATEGY", None)
        self.sns_topic_discovery = os.getenv("SNS_TOPIC_DISCOVERY", None)
        self.sns_sender = os.getenv("SES_SENDER", None)
        self.sns_recipient = os.getenv("SES_RECIPIENT", None)
        self.time_format = "%Y-%m-%dT%H:%M:%SZ"

        # Strategy Data
        self.daa_enter = os.getenv("STRATEGY_DAA_ENTER", None)
        self.daa_exit = os.getenv("STRATEGY_DAA_EXIT", None)
        self.sma_lookback = os.getenv("STRATEGY_SMA_LOOKBACK", None)
        self.volatility_enter = os.getenv("STRATEGY_VOLATILITY_ENTER", None)
        self.volatility_exit = os.getenv("STRATEGY_VOLATILITY_EXIT", None)

        self.validate()

    def validate(self):
        """
        Loads relevant env vars and assigns to self
        :return:
        """
        for k, v in self.__dict__.items():
            if v is None:
                raise Exception(f"Missing env var - key {k} value {v}")


