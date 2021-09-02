"""
signal_strategy.py
Converts a message from the Strategy Service into a more friendly format
"""
import json
from typing import Dict


class SignalStrategy:
    """
    Parse the SQS record into a useful format
    """

    def __init__(self, record: Dict):
        self.slug = record["body"]
        self.side = record["messageAttributes"]["side"]["stringValue"]
        self.ticker = record["messageAttributes"]["ticker"]["stringValue"]
        self.strategy_guid = record["messageAttributes"]["strategy_guid"]["stringValue"]
        self.ticker_kucoin = f"{record['messageAttributes']['ticker']['stringValue']}-USDT"

    def __repr__(self):
        return json.dumps(self.__dict__, indent=4)

    def to_dict(self):
        return self.__dict__
