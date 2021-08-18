"""
primer.py
Primer loads crypto slugs from the `TABLE_DISCOVERY`.
For each pair in the table:
    A queue item is created with:
        slug
        date_since last metrics harvested
        date_to (daily close) to harvested data. This is the right end point of the interval
"""
from internal.config.config import HarvestConfig
from internal.service_dynamo.dynamo import ServiceDynamo

HC = HarvestConfig()
DYNAMO = ServiceDynamo()


def primer(event, context):
    # Scan the dynamo table for pairs and last_udpated
    # Create SQS Items for each of the pairs
    all_tickers = DYNAMO.discovery_scan(HC.table_discovery)
    print(all_tickers)
