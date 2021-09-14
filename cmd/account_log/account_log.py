"""
account_log.py
Runs at fixed schedule to collect balance and trade information. Writes everything to the AccountLog table
Collects:
 Balance
 Available Balance
 Number Trades
"""
import datetime
import http
import json
import time

import kucoin.exceptions
import pandas as pd

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

    # Populate the table with all open trades, total values, and percentage of current account value
    try:
        time.sleep(15) # allow the API a cooloff period after the initail calls
        df = pd.DataFrame(ACCOUNT.client.get_accounts())
        df = df[df["balance"].astype(float) > 0.0001]
        df["prices"] = df["currency"].apply(lambda x: ACCOUNT.client.get_fiat_prices(symbol=x).get(x))
        df["total_value"] = df["balance"].astype(float) * df["prices"].astype(float)
        df["percent_of_account"] = df["total_value"] / df["total_value"].sum() * 100
        df["datetime"] = datetime.datetime.utcnow().strftime(HC.time_format)
        df = df[["currency", "balance", "available", "holds", "prices", "total_value", "percent_of_account", "datetime"]]

        for row in df.to_dict(orient="records"):
            item = DYNAMO.create_item_from_dict(row)
            DYNAMO.account_log_put_item(HC.table_account_position_log, item)

    except kucoin.exceptions.KucoinAPIException as e:
        if e.code == "503000":
            print(e.message)
            return {
                "statusCode": 503000,
                "body": json.dumps({
                    "message": e.message,
                })
            }

    return {
        "statusCode": http.HTTPStatus.OK,
        "body": json.dumps({
            "message": "Synced account logs to database",
        })
    }
