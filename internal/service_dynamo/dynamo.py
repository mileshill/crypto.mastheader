import datetime
from typing import Dict, Union, List
from math import floor

import boto3
from boto3.dynamodb.conditions import Key


class ItemDiscovery:
    def __init__(self, **kwargs):
        self.market_segment = kwargs.get("marketSegment", {}).get("S", None)
        self.ticker = kwargs.get("ticker", {}).get("S", None)
        self.slug = kwargs.get("slug", {}).get("S", None)
        self.datetime_last_updated = kwargs.get("datetimeLastUpdate", {}).get("S", "null")

    def to_sqs_format(self, delay_seconds: int = 0):
        return {
            "DelaySeconds": delay_seconds,
            "MessageBody": self.slug,
            "MessageAttributes": {
                "datetime_last_updated": {
                    "StringValue": self.datetime_last_updated,
                    "DataType": "String"
                },
                "ticker": {
                    "StringValue": self.ticker,
                    "DataType": "String"
                }
            }
        }


class ServiceDynamo:
    def __init__(self):
        self.client = boto3.client("dynamodb")
        self.resource = boto3.resource("dynamodb")

    def key_exists(self, tablename: str, hash_key_name: str, hash_key_type: str, hash_key_value: str) -> bool:
        """
        Check if the described hash key exists
        :param tablename:
        :param hash_key_name:
        :param hash_key_type:
        :param hash_key_value:
        :return:
        """
        resp = self.client.get_item(
            TableName=tablename,
            Key={
                hash_key_name: {hash_key_type: hash_key_value}
            }
        )
        item = resp.get("Item")
        if not item:
            return False
        return True

    def discovery_create_item(self, tablename: str, item: Dict[str, Dict[str, str]]):
        """
        Creates new item in the Discovery table
        :param tablename:
        :param data:
        :return:
        """
        resp = self.client.put_item(
            TableName=tablename,
            Item=item
        )
        return

    @staticmethod
    def create_item_from_dict(data: Dict) -> Dict:
        item = {}
        try:
            for k, v in data.items():
                if type(v) is dict and "S" in v:
                    item[k] = v["S"]
                    continue
                if type(v) in (float, int):
                    item[k] = {"N": str(v)}
                if type(v) is datetime.datetime:
                    item[k] = {"S": v.strftime("%Y-%m-%dT%H:%M:%SZ")}
                    continue
                else:
                    item[k] = {"S": str(v)}
            item["datetime_created"] = {"S": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
        except Exception as e:
            print(e)
            print("DATA: \n", data)
        return item

    def discovery_scan(self, tablename: str) -> List[ItemDiscovery]:
        items = list()
        scan_kwargs = {}
        done = False
        start_key = None
        while not done:
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key
            response = self.client.scan(
                TableName=tablename,
                Select="ALL_ATTRIBUTES"
            )
            items.extend(response.get("Items", []))
            start_key = response.get("LastEvaluatedKey", None)
            done = start_key is None
        items = [ItemDiscovery(**item) for item in items]
        return items

    def discovery_delete_item(self, tablename: str, slug: str) -> None:
        self.client.delete_item(
            TableName=tablename,
            Key={
                "slug": {"S": slug}
            }
        )
        return None

    def harvest_create_item(self, tablename: str, item: Dict[str, Dict[str, str]]):
        """
        Creates new item in the Discovery table
        :param tablename:
        :param data:
        :return:
        """
        resp = self.client.put_item(
            TableName=tablename,
            Item=item
        )
        return

    def harvest_get_last_update_for_slug(self, tablename: str, slug: str):
        table = self.resource.Table(tablename)
        response = table.query(
            Limit=1,
            ScanIndexForward=False,
            KeyConditionExpression=Key("slug").eq(slug)
        )
        return response["Items"][0]["datetime_metric"] if len(response["Items"]) else None

    def harvest_get_data_for_slug_within_range(self, tablename: str, slug: str, date_from: str, date_to: str) -> List[
        Dict]:
        table = self.resource.Table(tablename)
        response = table.query(
            KeyConditionExpression=Key("slug").eq(slug) & Key("datetime_metric").between(date_from, date_to)
        )
        return response["Items"] if len(response["Items"]) else None

    def strategy_meta_create_item(self, tablename: str, data: Dict[str, Union[str, float]]) -> None:
        """
        Creates new item in the Discovery table
        :param tablename:
        :param data:
        :return:
        """
        resp = self.client.put_item(
            TableName=tablename,
            Item={
                "slug": data["slug"],
                "guid": data["guid_meta"],
                "datetime_created": data["datetime_created"]
            }
        )
        return

    def strategy_details_create_item(self, tablename: str, data: Dict[str, Union[str, float]]) -> None:
        """
        Creates new item in the Discovery table
        :param tablename:
        :param data:
        :return:
        """
        resp = self.client.put_item(
            TableName=tablename,
            Item=data
        )
        return

    def strategy_meta_get_item(self, tablename: str, slug: str) -> Dict:
        """
        Check if the described hash key exists
        :param slug:
        :param tablename:
        :return:
        """
        resp = self.client.get_item(
            TableName=tablename,
            Key={
                "slug": {"S": slug}
            }
        )
        return resp["Item"]["guid"]["S"]

    def strategy_meta_delete_item(self, tablename: str, slug: str) -> None:
        self.client.delete_item(
            TableName=tablename,
            Key={
                "slug": {"S": slug}
            }
        )
        return None

    def account_get_max_position_size(self, tablename: str, account_name: str = "TRADE") -> float:
        resp = self.client.get_item(
            TableName=tablename,
            Key={
                "account_name": {"S": account_name}
            }
        )
        print(f"Response: account_get_max_position_size: {resp}")
        position_max = float(resp["Item"]["position_max"]["N"])
        balance_avail = float(resp["Item"]["balance_avail"]["N"])
        return min(position_max, balance_avail)

    def account_set_max_position_size(self, tablename: str, position_size: float, account_name: str = "TRADE"):
        resp = self.client.update_item(
            TableName=tablename,
            Key={
                "account_name": {"S": account_name},
            },
            AttributeUpdates={
                "position_max": {"Value": {"N": str(position_size)}, "Action": "PUT"}
            }
        )
        return

    def account_update_trades_open(self, tablename: str, account_name: str, num_open_trades: int):
        resp = self.client.update_item(
            TableName=tablename,
            Key={
                "account_name": {"S": account_name},
            },
            AttributeUpdates={
                "trades_open": {"Value": {"N": str(num_open_trades)}, "Action": "PUT"},
                "datetime_updated": {"Value": {"S": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}, "Action": "PUT"}
            }
        )
        return

    def account_get_trades_open(self, tablename: str, account_name: str):
        resp = self.client.get_item(
            TableName=tablename,
            Key={
                "account_name": {"S": account_name}
            }
        )
        if not resp.get("Item"):
            return None

        return int(resp.get("Item", {}).get("trades_open", {}).get("N", None))

    def account_update_available_balance(self, tablename: str, account_name: str, balance_avail: float):
        resp = self.client.update_item(
            TableName=tablename,
            Key={
                "account_name": {"S": account_name}
            },
            AttributeUpdates={
                "balance_avail": {"Value": {"N": str(balance_avail)}, "Action": "PUT"}
            }
        )

    def account_update(self, tablename: str, account_name: str, trades_max: int, trades_open: int, balance: float,
                       balance_avail: float, position_max: float):
        # Account does not exist
        resp = self.client.update_item(
            TableName=tablename,
            Key={
                "account_name": {"S": account_name}
            },
            AttributeUpdates={
                "trades_max": {"Value": {"N": str(trades_max)}, "Action": "PUT"},
                "trades_open": {"Value": {"N": str(trades_open)}, "Action": "PUT"},
                "balance": {"Value": {"N": str(balance)}, "Action": "PUT"},
                "balance_avail": {"Value": {"N": str(balance_avail)}, "Action": "PUT"},
                "position_max": {"Value": {"N": str(position_max)}, "Action": "PUT"},
                "datetime_created": {"Value": {"S": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")},
                                     "Action": "PUT"},
                "datetime_updated": {"Value": {"S": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")},
                                     "Action": "PUT"}
            }
        )
