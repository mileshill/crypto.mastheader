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
        self.queue_harvest = os.getenv("QUEUE_HARVEST", None)
        self.sns_topic_discovery = os.getenv("SNS_TOPIC_DISCOVERY", None)
        self.sns_sender = os.getenv("SES_SENDER", None)
        self.sns_recipient = os.getenv("SES_RECIPIENT", None)

        self.validate()

    def validate(self):
        """
        Loads relevant env vars and assigns to self
        :return:
        """
        for k, v in self.__dict__.items():
            if v is None:
                raise Exception(f"Missing env var - key {k} value {v}")


