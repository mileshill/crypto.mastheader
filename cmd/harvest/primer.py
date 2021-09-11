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
from random import shuffle
from internal import HC, DYNAMO
from internal.service_sqs.sqs import ServiceSQS

SQS = ServiceSQS(HC.queue_harvest)


def primer(event, context):
    # Scan the dynamo table for pairs and last_udpated
    # Create SQS Items for each of the pairs
    all_tickers = shuffle(DYNAMO.discovery_scan(HC.table_discovery))
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
