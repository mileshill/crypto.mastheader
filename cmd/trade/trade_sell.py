"""
trade_sell.py
Trade Sell implements the logic required to close an open position
"""
from collections import namedtuple

from internal.config.config import HarvestConfig
from internal.service_dynamo.dynamo import ServiceDynamo
from internal.service_kucoin.account import Account
from internal.service_sqs.signal_strategy import SignalStrategy

HC = HarvestConfig()
DYNAMO = ServiceDynamo()

Order = namedtuple("Order", ["order_id", "slug"])


def trade_sell(event, context):
    """
    Close any open trades
    :param event:
    :param context:
    :return:
    """
    account = Account(
        dynamo=DYNAMO, tablename=HC.table_account,
        key=HC.kucoin_key, secret=HC.kucoin_secret, api_pass_phrase=HC.kucoin_api_passphrase,
        max_trades=HC.strategy_max_trades,
        name="TRADE"
    )
    account.init_account()  # Calls to Kucoin to get current value

    # Create a dict for easy processing: { ticker: Signal, ...} -> { FRONT: Signal, XRP: Signal, Theta: Signal, ...}
    # Processes in batches
    strategy_signals = {
        record["messageAttributes"]["ticker"]["stringValue"]: SignalStrategy(record) for record in event["Records"]
    }

    orders = list()
    for kucoin_account in account.trade_accounts:
        # If there is no open position, there is nothing to close
        if kucoin_account.currency not in strategy_signals:  # kucoin_account.currency is the Base Ticker
            continue

        # Open sell order to close the position
        if kucoin_account.holds == kucoin_account.balance:
            continue

        # Create a new order to close the position
        order_id = account.create_limit_order_sell(
            symbol=f"{kucoin_account.currency}-USDT",
            price=kucoin_account.current_usdt,
            size=kucoin_account.balance
        )
        orders.append(
            Order(
                order_id=order_id.get("orderId"),
                slug=strategy_signals[kucoin_account.currency].slug
            )
        )

    # For each order, get the order and write to a dynamo table
    for order in orders:
        order_details = account.get_order(order.order_id)
        order_details["slug"] = order.slug
        item = DYNAMO.create_item_from_dict(order_details)
        DYNAMO.strategy_details_create_item(
            tablename=HC.table_trade_orders,
            data=item
        )
