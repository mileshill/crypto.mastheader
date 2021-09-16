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

from internal import HC, DYNAMO
from internal.service_sqs.sqs import ServiceSQS

SQSTradeBuy = ServiceSQS(HC.queue_trade_buy)
SQSTradeSell = ServiceSQS(HC.queue_trade_sell)


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
    df["sma"] = df["price_btc"].rolling(window=30).mean()

    # SMA daily derivative
    df["sma_derivative"] = df["sma"].diff()

    # Check for an all positive sma derivative for the strategy_sma_lookback
    df["sma_derivative_pos_trend"] = df["sma_derivative"] \
        .rolling(window=int(HC.strategy_sma_lookback)) \
        .apply(lambda data: all(sample > 0 for sample in data))

    # Absolute difference between price and SMA
    df["delta"] = (df["price_btc"] - df["sma"]) / df["sma"]
    df["volatility_enter_lower"] = df["delta"] < HC.strategy_volatility_enter_lower
    df["volatility_enter_upper"] = df["delta"] < HC.strategy_volatility_enter_upper
    df["volatility_enter"] = df["volatility_enter_lower"] & df["volatility_enter_upper"]
    df["volatility_exit"] = df["delta"] > HC.strategy_volatility_exit

    # Active Addresses Change
    df["daa_enter_lower"] = df["active_addresses_24h_change_1d"] >= HC.strategy_daa_enter_lower
    df["daa_enter_upper"] = df["active_addresses_24h_change_1d"] <= HC.strategy_daa_enter_upper
    df["daa_enter"] = df["daa_enter_lower"] & df["daa_enter_upper"]
    df["daa_exit"] = df["active_addresses_24h_change_1d"] < HC.strategy_daa_exit

    # Trending
    df["trending"] = (df["sma_derivative_pos_trend"] == 1) & (df["price_btc"] > df["sma"])

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
    # Contianers for SQS events used in batch publishing
    actions_buy = list()
    actions_sell = list()

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
            print(f"Slug({slug}) - No trade actions")
            return

        # Create the StrategyDetails entry
        guid_meta = str(uuid.uuid4())
        guid_details = f"{guid_meta}#{trade_action.value}"
        trade_conditions["datetime_proposed"] = datetime.datetime.utcnow().strftime(HC.time_format)
        trade_conditions["action"] = trade_action.value
        trade_conditions["guid_meta"] = guid_meta
        trade_conditions["guid_details"] = guid_details

        # Update the databases tables
        item = DYNAMO.create_item_from_dict(trade_conditions)
        DYNAMO.strategy_details_create_item(HC.table_strategy_details, item)

        # Message to transmit
        sqs_message = create_sqs_message(
            delay_seconds=0,
            message_body=slug,
            trade_action=trade_action.value,
            ticker=ticker,
            guid_details=guid_details
        )

        if trade_action == TradeAction.OPEN:
            actions_buy.append(sqs_message)
        if trade_action == TradeAction.CLOSE:
            actions_sell.append(sqs_message)

    SQSTradeSell.send_in_batches(actions_sell)
    SQSTradeBuy.send_in_batches(actions_buy)


def create_sqs_message(delay_seconds: int, message_body: str, trade_action: str, ticker: str,
                       guid_details: str) -> Dict:
    """
    Creates a dict in the format required by SQS to send messages in batches
    :param delay_seconds:
    :param message_body:
    :param trade_action:
    :param ticker:
    :param guid_details:
    :return:
    """
    return {
        "Id": str(uuid.uuid4()),
        "DelaySeconds": delay_seconds,
        "MessageBody": message_body,  # Should be the `slug`
        "MessageAttributes": {
            "side": {
                "StringValue": trade_action,  # trade_action.value to get str of enum
                "DataType": "String"
            },
            "ticker": {
                "StringValue": ticker,
                "DataType": "String"
            },
            "strategy_guid": {
                "StringValue": guid_details,
                "DataType": "String"
            }
        }
    }
