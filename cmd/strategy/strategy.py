"""
strategy.py
Triggered from an SQS event, load the relevent metrics from Dynamo and evaluate for
a trade action. If a trade action should be made, publish to an SNS topic, else, do nothing
"""
import datetime
import enum
import uuid
from typing import Dict

import pandas as pd

from internal.config.config import HarvestConfig
from internal.service_dynamo.dynamo import ServiceDynamo
from internal.service_sns.sns import ServiceSNS

HC = HarvestConfig()
DYNAMO = ServiceDynamo()
SNS = ServiceSNS()


class TradeAction(enum.Enum):
    OPEN = "open"
    CLOSE = "close"
    PASS = "pass"


def get_sma_lookback_date(datetime_last_updated: str, lookback: int) -> str:
    dt_last_updated = datetime.datetime.strptime(datetime_last_updated, HC.time_format)
    dt_lookback = dt_last_updated - datetime.timedelta(days=lookback + 30)  # SMA plus sufficient rolling window
    return dt_lookback.strftime(HC.time_format)


def compute_trade_conditions(df: pd.DataFrame) -> Dict:
    # Simple moving average
    df["sma"] = df["price_usd"].rolling(window=30).mean()

    # SMA daily derivative
    df["sma_derivative"] = df["sma"].diff()

    # Check for an all positive sma derivative for the strategy_sma_lookback
    df["sma_derivative_pos_trend"] = df["sma_derivative"] \
        .rolling(window=HC.strategy_sma_lookback) \
        .apply(lambda data: all(sample > 0 for sample in data))

    # Absolute difference between price and SMA
    df["delta"] = (df["price_usd"] - df["sma"]) / df["sma"]
    df["volatility_enter"] = df["delta"] < HC.strategy_volatility_enter
    df["volatility_exit"] = df["delta"] > HC.strategy_volatility_exit

    # Active Addresses Change
    df["daa_enter"] = df["active_addresses_24h_change_1d"] > HC.strategy_daa_enter
    df["daa_exit"] = df["active_addresses_24h_change_1d"] < HC.strategy_daa_exit

    # Trending
    df["trending"] = (df["sma_der_pos"] == 1) & (df["price_usd"] > df["sma"])

    # Trade actions
    df["trade_open"] = df["daa_enter"] & df["trending"] & df["volatility_enter"]
    df["trade_close"] = df["daa_exit"] | df["volatility_exit"] | ~df["trending"]

    return df.iloc[-1].to_dict()


def get_trade_action(row: Dict) -> TradeAction:
    trade_open = row["trade_open"]
    trade_close = row["trade_close"]

    if trade_open:
        return TradeAction.OPEN
    if trade_close:
        return TradeAction.CLOSE
    return TradeAction.PASS


def strategy(event, context):
    for record in event["Records"]:
        slug = record["body"]
        ticker = record["messageAttributes"]["ticker"]["stringValue"]
        date_to = record["messageAttributes"]["datetime_last_updated"]["stringValue"]
        date_from = get_sma_lookback_date(date_to, HC.strategy_sma_lookback)

        # 1. Load data for the given slug between the datetime_last_update and datetime_lookback
        items = DYNAMO.harvest_get_data_for_slug_within_range(HC.table_harvest, slug, date_from, date_to)
        if items is None:
            print(f"NO DATA - Table {HC.table_harvest}, Slug {slug}, DateFrom {date_from}, DateTo: {date_to}")
            return

        # 2. Convert items list to dataframe. Implement the trade action decision pattern
        df = pd.DataFrame(items)
        for col in df.columns:
            if "datetime" in col or "slug" in col:
                continue
            df[col] = df[col].astype(float)  # Covert decimals

        # Key
        df["slug"] = slug
        trade_conditions = compute_trade_conditions(df)
        trade_action = get_trade_action(trade_conditions)

        # Trade decisions
        if trade_action == TradeAction.PASS:
            print(f"Slug({slug} - No trade actions")
            return

        # Trade Open
        should_publish_to_sns = False
        if trade_action == TradeAction.OPEN:
            """
            if not (trade_open_for_slug):
                open the trade in meta and details
            else pass 
            """
            # Check for an active trade. If not exists, open, else return
            guid_meta = str(uuid.uuid4())
            guid_details = f"{guid_meta}#{trade_action.value}"
            trade_conditions["datetime_proposed"] = datetime.datetime.utcnow().strftime(HC.time_format)
            trade_conditions["action"] = trade_action.value
            trade_conditions["guid_meta"] = guid_meta
            trade_conditions["guid_details"] = guid_details
            should_publish_to_sns = True
            # TODO
            # 1. Write to StrategyMeta (slug, guid)
            # 2. Write to StrategyDetails (slug, guid_details

        if trade_action == TradeAction.CLOSE:
            """
             if (trade_open_for_slug):
                 close the trade by deleting index from meta and completing the details 
            else pass
            """
            should_publish_to_sns = True
            pass

        if should_publish_to_sns:
            SNS.send_message(topic=HC.sns_topic_strategy, message={
                "Subject": slug,
                "Message": trade_action.value,
                "MessageAttributes": {
                    "action_guid": {
                        "DataType": "String",
                        "StringValue": trade_action.value
                    }
                }
            })
