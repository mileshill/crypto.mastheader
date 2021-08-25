import os
from .account import Account


class TestAccount:
    os_vars = {
        "key": os.getenv("KUCOIN_KEY"),
        "secret": os.getenv("KUCOIN_SECRET"),
        "api_pass_phrase": os.getenv("KUCOIN_API_PASSPHRASE")
    }

    account = Account(**os_vars)
    print(account)

