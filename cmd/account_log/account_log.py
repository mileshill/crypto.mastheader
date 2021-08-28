"""
account_log.py
Runs at fixed schedule to collect balance and trade information. Writes everything to the AccountLog table
Collects:
 Balance
 Available Balance
 Number Trades
"""
import datetime

from internal.config.config import HarvestConfig
from internal.service_dynamo.dynamo import ServiceDynamo
from internal.service_kucoin.account import Account

HC = HarvestConfig()
DYNAMO = ServiceDynamo()


def account_log(event, context):
    # Default account initialization
    account = Account(
        dynamo=DYNAMO, tablename=HC.table_account,
        key=HC.kucoin_key, secret=HC.kucoin_secret, api_pass_phrase=HC.kucoin_api_passphrase,
        max_trades=HC.strategy_max_trades,
        name="TRADE"
    )
    account.init_account()  # Makes the calls to Kucoin

    # Desire info
    details = {
        "account_name": account.name,
        "balance": account.balance,
        "balance_avail": account.balance_avail,
        "position_max": account.position_max,
        "trades_open": account.trades_open,
        "datetime": datetime.datetime.utcnow().strftime(HC.time_format)
    }

    # Log to dynamo
    item = DYNAMO.create_item_from_dict(details)
    DYNAMO.account_log_put_item(HC.table_account_log, item)
    return
