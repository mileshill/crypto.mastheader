import os
from .account import Account


class TestAccount:
    config = {
        "key": os.getenv("KUCOIN_KEY"),
        "secret": os.getenv("KUCOIN_SECRET"),
        "api_pass_phrase": os.getenv("KUCOIN_API_PASSPHRASE"),
        "max_trades": 10
    }
    account = Account(**config)
    print(account)

