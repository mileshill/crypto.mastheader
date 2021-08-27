"""
primer.py
Primer loads crypto slugs from the `TABLE_DISCOVERY`.
For each pair in the table:
    A queue item is created with:
        slug
        date_since last metrics harvested
        date_to (daily close) to harvested data. This is the right end point of the interval
"""
import http
import json

from internal.config.config import HarvestConfig
from internal.service_dynamo.dynamo import ServiceDynamo
from internal.service_sqs.sqs import ServiceSQS

HC = HarvestConfig()
DYNAMO = ServiceDynamo()
SQS = ServiceSQS(HC.queue_harvest)


def primer(event, context):

    # Scan the dynamo table for pairs and last_udpated
    # Create SQS Items for each of the pairs
    all_tickers = DYNAMO.discovery_scan(HC.table_discovery)
    if HC.env.upper() == "DEV" or HC.env.upper() == "TEST":
        print(f"Slicing all tickers to reduce SAN API Usage. ENV: {HC.env}")
        all_tickers = all_tickers
    message_ids = [
        SQS.send_message(item.to_sqs_format(delay_seconds=min(delay * 3, 900)))
        for delay, item in enumerate(all_tickers)
    ]

    return {
        "statusCode": http.HTTPStatus.OK,
        "body": json.dumps({
            "message_ids": message_ids
        })
    }
