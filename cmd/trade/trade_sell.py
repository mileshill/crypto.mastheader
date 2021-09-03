"""
trade_sell.py
Trade Sell implements the logic required to close an open position
"""
from collections import namedtuple

import kucoin.exceptions

from internal.config.config import HarvestConfig
from internal.service_dynamo.dynamo import ServiceDynamo
from internal.service_kucoin.account import Account
from internal.service_sqs.signal_strategy import SignalStrategy

HC = HarvestConfig()
DYNAMO = ServiceDynamo()

Order = namedtuple("Order", ["order_id", "slug", "strategy_guid"])

ACCOUNT = Account(
    dynamo=DYNAMO, tablename=HC.table_account,
    key=HC.kucoin_key, secret=HC.kucoin_secret, api_pass_phrase=HC.kucoin_api_passphrase,
    max_trades=HC.strategy_max_trades,
    name="TRADE"
)


def trade_sell(event, context):
    """
    Close any open trades
    :param event:
    :param context:
    :return:
    """
    ACCOUNT.init_account()  # Calls to Kucoin to get current value
    # Create a dict for easy processing: { ticker: Signal, ...} -> { FRONT: Signal, XRP: Signal, Theta: Signal, ...}
    # Processes in batches
    strategy_signals = {
        record["messageAttributes"]["ticker"]["stringValue"]: SignalStrategy(record) for record in event["Records"]
    }

    orders = list()
    for kucoin_account in ACCOUNT.trade_accounts:
        # If there is no open position, there is nothing to close
        if kucoin_account.currency not in strategy_signals:  # kucoin_account.currency is the Base Ticker
            continue

        # Open sell order to close the position
        if kucoin_account.holds == kucoin_account.balance:
            print(
                f"{kucoin_account.currency}-USDT has open order. Holds: {kucoin_account.holds} Balance: {kucoin_account.balance}")
            continue

        # Create a new order to close the position
        try:
            print(
                f"Sell: {kucoin_account.currency}-USDT Price:{kucoin_account.current_usdt} Size: {kucoin_account.balance}")
            order_id = ACCOUNT.create_limit_order_sell(
                symbol=f"{kucoin_account.currency}-USDT",
                price=kucoin_account.current_usdt,
                size=kucoin_account.balance
            )
            orders.append(
                Order(
                    order_id=order_id.get("orderId"),
                    slug=strategy_signals[kucoin_account.currency].slug,
                    strategy_guid=strategy_signals[kucoin_account.currency].strategy_guid
                )
            )
        except kucoin.exceptions.KucoinAPIException as e:
            if e.code == "900001":
                print(f"{strategy_signals[kucoin_account.currency].slug}-USDT not exist")
                print(e)
                continue
            raise e
    # For each order, get the order details and write to a dynamo table
    for order in orders:
        order_details = ACCOUNT.get_order(order.order_id)
        order_details["slug"] = order.slug
        order_details["strategy_guid"] = order.strategy_guid
        item = DYNAMO.create_item_from_dict(order_details)
        DYNAMO.strategy_details_create_item(
            tablename=HC.table_orders,
            data=item
        )
