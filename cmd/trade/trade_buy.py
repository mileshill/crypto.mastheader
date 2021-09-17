"""
trade_buy.py
Trade Buy implments the logic required to open a position
"""
from collections import namedtuple

import kucoin.exceptions

from internal import HC, DYNAMO, ACCOUNT
from internal.service_sqs.signal_strategy import SignalStrategy

Order = namedtuple("Order", ["order_id", "slug", "strategy_guid"])


def trade_buy(event, context):
    strategy_signals = {
        record["messageAttributes"]["ticker"]["stringValue"]: SignalStrategy(record) for record in event["Records"]
    }
    # No reason to process further if the account cannot trade
    if not ACCOUNT.can_trade():
        print(
            f"Account cannot trade. MaxPositions: {ACCOUNT.trades_max} OpenPositions: {ACCOUNT.trades_open} MaxTrade: {ACCOUNT.position_max} AvailBalance: {ACCOUNT.balance_avail}")
        return

    # Delete those strategy signals where open positions already exist
    for kucoin_account in ACCOUNT.trade_accounts:
        # Already an open position
        if kucoin_account.currency in strategy_signals:
            del strategy_signals[kucoin_account.currency]
            continue

    orders = list()
    for signal in strategy_signals.values():
        if ACCOUNT.has_active_buy_order_for_symbol(signal.ticker_kucoin):
            print(f"{signal.slug} has open buy order")
            continue

        # No open position. No active orders. But account is maxed on trades or not enough balance
        # Yes, it was checked above. But if a sell has happened and there is sufficient balance for more
        # than a single order, this should be checked again. The account is reinitialized after each buy order is placed
        # to ensure correct values
        if not ACCOUNT.can_trade():
            print(
                f"Account cannot trade: NumOpenTrades: {ACCOUNT.trades_open} BalanceAvail: {ACCOUNT.balance_avail} Position Max: {ACCOUNT.position_max} SLUG: {signal.slug}")
            continue

        # Finally. Time to create a buy order
        position_size = ACCOUNT.get_position_size_max()
        print("Position Size: ", position_size)
        price, size = ACCOUNT.compute_price_and_size(
            symbol=signal.ticker,
            position_size=position_size
        )
        if price is None or size is None:
            print("No price or size. Dropping")
            continue

        print(f"Avail: {ACCOUNT.balance_avail} PositionSize: {position_size} Price: {price} Size: {size}")
        try:
            print(f"Buy: {signal.ticker_kucoin} Price: {price} Size: {size}")
            order_id = ACCOUNT.create_limit_order_buy(
                symbol=f"{signal.ticker}-BTC",
                price=price,
                size=size
            )
            orders.append(
                Order(
                    order_id=order_id.get("orderId"),
                    slug=signal.slug,
                    strategy_guid=signal.strategy_guid
                )
            )
            ACCOUNT.init_account()
        except kucoin.exceptions.KucoinAPIException as e:
            if e.code == "900001":
                print(f"{signal.slug}: {signal.ticker_kucoin} does not exist")
                continue
            raise e

    # For each order, get the order details and write to dynamo
    for order in orders:
        order_details = ACCOUNT.get_order(order.order_id)
        order_details["slug"] = order.slug
        order_details["strategy_guid"] = order.strategy_guid
        item = DYNAMO.create_item_from_dict(order_details)
        DYNAMO.strategy_details_create_item(
            tablename=HC.table_orders,
            data=item
        )
