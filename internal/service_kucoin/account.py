"""
account.py
Implements the basic account computations required create trades.
"""
from typing import List, Dict, Union
from kucoin.client import Client


class KuCoinAcct:
    def __init__(self, id: str, currency: str, type: str, balance: str, available: str, holds: str):
        self.id = id
        self.currency = currency
        self.account_type = type
        self.balance = float(balance)
        self.available = float(available)
        self.holds = float(holds)
        self.current_usdt = None

    def get_usdt_equivalent(self, client: Client) -> float:
        current_usdt = client.get_fiat_prices(symbol=self.currency)
        self.current_usdt = float(current_usdt[self.currency])  # Set on object to cut down on calls
        return self.current_usdt


class Account:
    def __init__(self, key: str, secret: str, api_pass_phrase: str):
        self.client = Client(key, secret, api_pass_phrase)
        self._trade_accounts = self._get_trade_accounts()

        self.current_balance = self.get_trade_balance_total()
        self.current_balance_avail = self.get_trade_balance_available()

    def _get_trade_accounts(self) -> List[KuCoinAcct]:
        return [
            KuCoinAcct(**act) for act in self.client.get_accounts()
            if ((float(act["balance"]) > 0) and (act["type"] == "trade"))  # Nonzero traiding pairs
            or ((act["currency"] == "USDT") and (act["type"] == "trade"))  # Just USDT
        ]

    def get_trade_balance_total(self) -> float:
        """
        Summation of all trading pairs convert to usdt-equivalent
        :return:
        float
        """
        # Trade accounts with non-zero balance
        return sum(
            acct.get_usdt_equivalent(self.client) * acct.balance
            for acct in self._trade_accounts
        )

    def get_trade_balance_available(self) -> Union[float, None]:
        """
        Amount of USDT available to trade
        :return:
        """
        for acct in self._trade_accounts:
            if acct.currency == "USDT":
                return acct.available
        return None
