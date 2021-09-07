"""
account.py
Implements the basic account computations required create trades.
"""
from typing import List, Union, Tuple, Dict

import boto3
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

    def to_dict(self):
        return self.__dict__

    def get_usdt_equivalent(self, client: Client, override: bool = False) -> float:
        current_usdt = client.get_fiat_prices(symbol=self.currency)
        self.current_usdt = float(current_usdt[self.currency])  # Set on object to cut down on calls
        return self.current_usdt


class Symbol:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            self.__setattr__(key, value)


class Account:
    def __init__(self, dynamo: boto3.client, tablename: str, key: str, secret: str, api_pass_phrase: str,
                 max_trades: int = 10, name: str = "TRADE"):
        self.dynamo = dynamo
        self.tablename = tablename
        self.trades_max = max_trades
        self.name = name or "TRADE"
        self.key = key
        self.secret = secret
        self.api_pass_phrase = api_pass_phrase

        self.client = None
        self.symbols = None
        self.trade_accounts = None
        self.trades_open = None
        self.balance = None
        self.balance_avail = None
        self.position_max = None
        self.orders_open_sell = None

    def init_account(self):
        """
        Make calls to Kucoin to get the most relevant info.
        Once calls are made, update the dynamo table

        :return:
        """
        # Init the KuCoin client.
        # Load trades, total balance, and available balance
        self.client = Client(self.key, self.secret, self.api_pass_phrase)
        self.symbols = [Symbol(**symbol) for symbol in self.client.get_symbols()]
        self.trade_accounts = self.get_trade_accounts()  # All non-zero trade accounts
        self.trades_open = self.get_trades_open()  # All non-zero trade accounts NOT USDT
        self.balance = self.get_trade_balance_total()  # All trade account balances converted to USDT
        self.balance_avail = self.get_trade_balance_available()  # Available USDT
        self.orders_open_sell = self.get_open_sell_orders()

        # Make any updates to dynamo
        self.dynamo.account_update(
            self.tablename, account_name=self.name,
            trades_max=self.trades_max, trades_open=self.trades_open,
            balance=self.balance, balance_avail=self.balance_avail,
            position_max=(self.balance / self.trades_max)
        )

        self.position_max = int(self.balance / self.trades_max)

    def get_open_sell_orders(self) -> List[str]:
        return [
            item.get("symbol") for item in
            self.client.get_orders(side=self.client.SIDE_SELL, status="active").get("items")
        ]

    def to_dict(self):
        dict_copy = {**self.__dict__}
        del dict_copy["client"]
        del dict_copy["dynamo"]
        del dict_copy["secret"]
        del dict_copy["api_pass_phrase"]
        trade_accounts = dict_copy.get("trade_accounts")
        dict_copy["trade_accounts"] = [a.to_dict() for a in trade_accounts]
        return dict_copy

    def can_trade(self) -> bool:
        """
        If trades_open < trades_max and there is balance_available True else False
        Assume at least 1 USDT is available for trade.
        :return:
        bool
        """
        if self.trades_open >= self.trades_max:
            return False
        if self.balance_avail < self.position_max * 0.5:
            return False
        return True

    def get_price_increment_for_symbol(self, ticker_kucoin: str) -> int:
        for symbol in self.symbols:
            if symbol.symbol == ticker_kucoin:
                increment = symbol.priceIncrement  # String value "0.0001"
                num_decimals = increment.split(".")[-1]
                return len(num_decimals) - 1
        return 4  # small enough for most all trading pairs (just in case)

    def get_base_increment_for_symbol(self, ticker_kucoin: str) -> int:
        for symbol in self.symbols:
            if symbol.symbol == ticker_kucoin:
                increment = symbol.baseIncrement
                num_decimals = increment.split(".")[-1]
                return len(num_decimals)
        return 4

    def get_trade_accounts(self) -> List[KuCoinAcct]:
        """
        Get list of all TRADE accounts where balance is above a near-zero threshold
        :return:
        List of KuCoinAcct objects
        """
        return [
            KuCoinAcct(**act) for act in self.client.get_accounts()
            if ((float(act["balance"]) > 0.01) and (act["type"] == "trade"))  # Nonzero traiding pairs
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
            for acct in self.trade_accounts
        )

    def get_trade_balance_available(self) -> Union[float, None]:
        """
        Amount of USDT available to trade
        :return:
        Amount of USDT or None
        """
        for acct in self.trade_accounts:
            if acct.currency == "USDT":
                return acct.available
        return None

    def update_trade_balance_available(self, balance_avail: float) -> None:
        self.balance_avail = balance_avail
        self.dynamo.account_update_available_balance(self.tablename, self.name, balance_avail)
        return

    def increment_trades_open(self):
        self.trades_open += 1
        self.dynamo.account_update_trades_open(self.tablename, self.name, self.trades_open)

    def get_trades_open(self):
        """
        Any account where the curreny is not USDT
        :return:
        """
        return sum(1 for acct in self.trade_accounts if acct.currency not in ["USDT", "KCS"])

    def compute_price_and_size(self, symbol: str, position_size: float) -> Tuple[float, float]:
        """
        Trades are placed in the base currency. BTC-USDT: BTC is the base. USDT is the quote
        To place a trade, the USDT position size must be converted to the corresponding amount in the
        base pair.
        :param symbol:
        :param position_size: number of dollars to spend
        :return:
        """
        quote_usdt = float(self.client.get_fiat_prices(symbol=symbol)[symbol])
        return quote_usdt, position_size / quote_usdt

    def create_limit_order_buy(self, symbol: str, price: float, size: float) -> Union[Dict[str, str], None]:
        """
        Creation of limit order to buy. Order is good for 1 hour
        :param size:  how many to buy
        :param price:  price in USDT to place the order
        :param symbol: trading pair
        :return:
        """
        # Make sure a position is not added too
        if any(symbol == acct.currency for acct in self.trade_accounts):
            return
        increment_price = self.get_price_increment_for_symbol(symbol)
        increment_quote = self.get_base_increment_for_symbol(symbol)
        print(
            f"Buy Order: {symbol} Price: {round(price, increment_price)} Size: {round(size, increment_quote)}")
        order_id = self.client.create_limit_order(
            symbol=symbol,
            side=self.client.SIDE_BUY,
            price=f"{round(price, increment_price)}",
            size=f"{round(size, increment_quote)}",
            time_in_force=self.client.TIMEINFORCE_GOOD_TILL_TIME,
            cancel_after=str(3600)  # Cancel after 1 hour
        )
        print(f"OrderId: {order_id}")
        return order_id

    def create_limit_order_sell(self, symbol: str, price: float, size: float) -> Union[Dict[str, str], None]:
        """
        Creates limit order to sell. Good till canceled
        :param symbol:
        :param price:
        :param size:
        :return:
        """
        # Make sure position is not added too
        if any(symbol == acct.currency for acct in self.trade_accounts):
            return

        increment_price = self.get_price_increment_for_symbol(symbol)
        increment_quote = self.get_base_increment_for_symbol(symbol)
        try:
            print(f"SELL Order: {symbol} Price: {str(price)} Quote: {price / size:.6f} Increment: {increment_price}")
        except ZeroDivisionError:
            pass
        order_id = self.client.create_limit_order(
            symbol=symbol,
            side=self.client.SIDE_SELL,
            price=f"{round(price, increment_price)}",
            size=f"{round(size, increment_quote)}",
            time_in_force=self.client.TIMEINFORCE_GOOD_TILL_CANCELLED,
        )
        return order_id

    def get_open_position_by_symbol(self, symbol: str) -> Union[KuCoinAcct, None]:
        for acct in self.trade_accounts:
            if acct.currency == symbol:
                return acct
        return

    def get_position_size_max(self):
        position_max_from_db = self.dynamo.account_get_max_position_size(
            self.tablename, self.name
        )
        return int(min(position_max_from_db, self.balance_avail)) - 1

    def get_order(self, order_id: str) -> Dict:
        return self.client.get_order(order_id)

    def has_active_buy_order_for_symbol(self, symbol: str) -> bool:
        if "-USDT" not in symbol:
            symbol = f"{symbol}-USDT"

        items = self.client.get_orders(
            side=self.client.SIDE_BUY,
            symbol=symbol,
            status="active"
        ).get("items")
        return bool(items)

