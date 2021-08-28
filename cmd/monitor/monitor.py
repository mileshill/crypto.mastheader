"""
monitor.py
Monitor tracks open trades.  Should be triggered by single events due to the timeout visibility
If open buy trades are canceled after their 1 hour lifetime, their details are removed from tradeMeta and tradeDetails.
If open sell trades are filled, delete them from tradeMeta.

If an item should not complete, delete receiptHandle and re-add to queue

Once orders have filled, send a message to the TwitterBot to make a post about entry and exit

"""
from typing import Dict

from kucoin.client import Client

from internal.config.config import HarvestConfig
from internal.service_dynamo.dynamo import ServiceDynamo
from internal.service_sqs.sqs import ServiceSQS

HC = HarvestConfig()
DYNAMO = ServiceDynamo()
SQSMonitor = ServiceSQS(HC.queue_monitor)


class SQSMessage:
    def __init__(self, record: Dict):
        self.slug = record["slug"]
        self.guid_meta = record["messageAttributes"]["guid_meta"]["stringValue"]
        self.guid_details = record["messageAttributes"]["guid_details"]
        self.order_id = record["messageAttributes"]["order_id"]["stringValue"]


def get_kucoin_client(key: str, secret: str, api_pass_phrase: str) -> Client:
    return Client(api_key=key, api_secret=secret, passphrase=api_pass_phrase)


def monitor(event, context):
    client = get_kucoin_client(HC.kucoin_secret, HC.kucoin_key, HC.kucoin_api_passphrase)
    for record in event["Records"]:
        print(record)
        msg = SQSMessage(record)
        order = client.get_order(msg.order_id)

        order_is_active = order.get("isActive")
        order_is_cancelled = order.get("cancelExist")
        order_side = order.get("side")

        # For BUY side
        if order_side == "buy":
            if order_is_active:
                # Still waiting on fill or timeout
                # Send back to SQS
                pass
            if not order_is_active and order_is_cancelled:
                # Did not fill due to time constraint
                pass
            if order_is_active and not order_is_cancelled:
                # Order filled
                pass

        # For SELL side
        if order_side == "sell":
            if order_is_active:
                # Still waiting. HOw long should it wait before changing the order?
                pass
            if not order_is_active:
                # Fill occurred
                pass

        print(f"Done! No errors occurred for slug {msg.slug}")


