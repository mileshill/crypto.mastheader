import json
import uuid
from itertools import chain
from typing import List, Dict

import kucoin.exceptions

from internal.config.config import HarvestConfig
from internal.service_dynamo.dynamo import ServiceDynamo
from internal.service_kucoin.account import Account
from internal.service_sns.sns import ServiceSNS
from internal.service_sqs.sqs import ServiceSQS

HC = HarvestConfig()
DYNAMO = ServiceDynamo()
SNS = ServiceSNS()
SQSTrade = ServiceSQS(HC.queue_trade)
SQSMonitor = ServiceSQS(HC.queue_monitor)


class Signal:
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


def process_signals_sell(account: Account, signals_sell: List[Signal]) -> List[Dict]:
    """

    :param account: Accounting tool
    :param signals_sell: SQS events from Strategy to close
    :return:
    """
    orders = []
    for signal in signals_sell:
        # For a signal to be a sell signal, it must meet the following:
        # 1. Show a balance in KuCoin
        # 2. Be represented in the tradeMeta table by the slug
        kucoin_acct = account.get_open_position_by_symbol(signal.ticker)
        # exists_in_db = DYNAMO.key_exists(
        #     HC.table_trade_meta,
        #     hash_key_name="slug", hash_key_type="S", hash_key_value=signal.slug
        # )

        if kucoin_acct is None: #or not exists_in_db:
            print(f"No open account for closing signal on slug: {signal.slug}")
            print(json.dumps(signal.to_dict(), indent=4))
            continue

        # Trade shows as open. Time to close!
        # No time limit on closing (yet)
        # TODO: should there be a time-to-expire on closing? Shift to market or adjust price?
        order_id = account.create_limit_order_sell(
            symbol=signal.ticker_kucoin,
            price=kucoin_acct.current_usdt,
            size=kucoin_acct.available
        )

        # Get the meta item for updating
        guid_meta = DYNAMO.strategy_meta_get_item(HC.table_trade_meta, signal.slug)
        trade_details = {
            "guid_meta": guid_meta,
            "guid_details": f"{guid_meta}#close",
            "order_id": order_id,
            **signal.to_dict()
        }
        item = DYNAMO.create_item_from_dict(trade_details)
        DYNAMO.strategy_details_create_item(HC.table_trade_details, item)  # Create the closing arg
        orders.append(trade_details)
    return orders


def process_signals_buy(account: Account, signals_buy: List[Signal]) -> List[Dict]:
    orders = []
    for signal in signals_buy:
        if not account.can_trade(signal.slug):
            continue
        # Account can only trade based on max trades and if that given trade is not yet open

        price, size = account.compute_price_and_size(
            symbol=signal.ticker,
            position_size=account.get_position_size_max()
        )
        # Create the limit order
        print(f"Creating BUY order for {signal.slug}")
        try:
            order_id = account.create_limit_order_buy(
                symbol=signal.ticker_kucoin,
                price=price,
                size=size
            )
        except kucoin.exceptions.KucoinAPIException as e:
            print(e)
            continue

        guid_meta = str(uuid.uuid4())
        trade_details = {
            "guid_meta": guid_meta,
            "guid_details": f"{guid_meta}#open",
            "order_id": order_id,
            **signal.to_dict()
        }
        orders.append(trade_details)

        # Create the items for tracking the trade
        item = DYNAMO.create_item_from_dict(trade_details)
        DYNAMO.strategy_details_create_item(HC.table_trade_details, item)
        DYNAMO.strategy_meta_create_item(HC.table_trade_meta, item)

        # Account bookkeeping
        account.update_trade_balance_available(account.balance_avail - account.position_max)
        account.increment_trades_open()
        account.init_account()  # Force Kucoin API calls to rebalnce
    return orders


def trade(event, context):
    """
    Signals from SQS should be processed in batch to limit Kucoin API call limitations
    :param event:
    :param context:
    :return:
    """
    # One account for the batch of signals
    account = Account(
        dynamo=DYNAMO, tablename=HC.table_account,
        key=HC.kucoin_key, secret=HC.kucoin_secret, api_pass_phrase=HC.kucoin_api_passphrase,
        max_trades=HC.strategy_max_trades,
        name="TRADE"
    )
    account.init_account()  # Calls to Kucoin to get current value
    # Might be the first time seeing the account

    # Event Records are coming in maximum of 10 batches.
    # Processed in batch to help prevent slamming the KuCoin Rate-Limit
    signals_buy = []
    signals_sell = []
    for record in event["Records"]:
        # These are SQS events
        signal = Signal(record)
        if signal.side == "open":
            signals_buy.append(signal)
        if signal.side == "close":
            signals_sell.append(signal)
    print("PreProcessing")
    print("BUY: ", signals_buy)
    print("SELL: ", signals_sell)

    signals_sell = process_signals_sell(account, signals_sell)
    signals_buy = process_signals_buy(account, signals_buy)

    print("PostProcessing")
    print("BUY: ", signals_buy)
    print("SELL: ", signals_sell)

    # Clear the Trade Queue
    for record in event["Records"]:
        SQSTrade.delete_message(
            receipt_handle=record["receiptHandle"]
        )
    # Push orders to monitoring so the balances can be updated
    for trade_detail in chain(signals_sell, signals_buy):
        SQSMonitor.send_message({
            "DelaySeconds": 900,
            "MessageBody": trade_detail["slug"],
            "MessageAttributes": {
                key: {
                    "StringValue": value,
                    "DataType": "String"
                } for key, value in trade_detail.items()
            }
        })


