import datetime
from typing import Dict, Union, List

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
        for k, v in data.items():
            if type(v) in (str, bool):
                item[k] = {"S": str(v)}
                continue
            item[k] = {"N": str(v)}
        item["datetime_created"] = {"S": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
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
        return resp["Item"]["guid"]

    def strategy_meta_delete_item(self, tablename: str, slug: str) -> None:
        self.client.delete_item(
            TableName=tablename,
            Key={
                "slug": {"S": slug}
            }
        )
        return None
