import datetime
from typing import Dict, Union, List

import boto3


class ServiceDynamo:
    def __init__(self):
        self.client = boto3.client("dynamodb")

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

    def discovery_create_item(self, tablename: str, data: Dict[str, Union[str, float]]):
        """
        Creates new item in the Discovery table
        :param tablename:
        :param data:
        :return:
        """
        resp = self.client.put_item(
            TableName=tablename,
            Item={
                "slug": {"S": data["slug"]},
                "marketSegment": {"S": data["marketSegment"]},
                "name": {"S": data["name"]},
                "ticker": {"S": data["ticker"]},
                "totalSupply": {"N": data["totalSupply"]},
                "timestampCreated": {"N": str(int(datetime.datetime.utcnow().timestamp()))},
                "datetimeCreated": {"S": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
            }
        )
        return

    def discovery_scan(self, tablename: str) -> List[Dict]:
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
        return items
