"""
account_log.py
Runs at fixed schedule to collect balance and trade information. Writes everything to the AccountLog table
Collects:
 Balance
 Available Balance
 Number Trades
"""
import datetime

from internal import HC, DYNAMO, ACCOUNT


def account_log(event, context):
    # Default account initialization
    ACCOUNT.init_account()
    # Desire info
    details = {
        "account_name": ACCOUNT.name,
        "balance": ACCOUNT.balance,
        "balance_avail": ACCOUNT.balance_avail,
        "position_max": ACCOUNT.position_max,
        "trades_open": ACCOUNT.trades_open,
        "datetime": datetime.datetime.utcnow().strftime(HC.time_format)
    }

    # Log to dynamo
    item = DYNAMO.create_item_from_dict(details)
    DYNAMO.account_log_put_item(HC.table_account_log, item)
    return
