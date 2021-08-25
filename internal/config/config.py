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
        self.table_strategy_meta = os.getenv("TABLE_STRATEGY_META", None)
        self.table_strategy_details = os.getenv("TABLE_STRATEGY_DETAILS", None)
        self.queue_harvest = os.getenv("QUEUE_HARVEST", None)
        self.queue_strategy = os.getenv("QUEUE_STRATEGY", None)
        self.sns_topic_discovery = os.getenv("SNS_TOPIC_DISCOVERY", None)
        self.sns_topic_strategy = os.getenv("SNS_TOPIC_STRATEGY", None)
        self.sns_sender = os.getenv("SES_SENDER", None)
        self.sns_recipient = os.getenv("SES_RECIPIENT", None)
        self.time_format = "%Y-%m-%dT%H:%M:%SZ"
        self.env = os.getenv("ENV", None)

        # Kucoin
        self.kucoin_key = os.getenv("KUCOIN_KEY")
        self.kucoin_secret = os.getenv("KUCOIN_SECRET")
        self.kucoin_api_passphrase = os.getenv("KUCOIN_API_PASSPHRASE")

        # Strategy Data
        self.strategy_daa_enter = os.getenv("STRATEGY_DAA_ENTER", None)
        self.strategy_daa_exit = os.getenv("STRATEGY_DAA_EXIT", None)
        self.strategy_sma_lookback = os.getenv("STRATEGY_SMA_LOOKBACK", None)
        self.strategy_volatility_enter = os.getenv("STRATEGY_VOLATILITY_ENTER", None)
        self.strategy_volatility_exit = os.getenv("STRATEGY_VOLATILITY_EXIT", None)
        self.validate()

    def validate(self):
        """
        Loads relevant env vars and assigns to self
        :return:
        """
        for k, v in self.__dict__.items():
            if k.startswith("strategy"):
                self.__dict__[k] = float(v)
            if v is None:
                raise Exception(f"Missing env var - key {k} value {v}")


