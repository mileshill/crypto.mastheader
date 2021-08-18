"""
primer.py
Primer loads crypto slugs from the `TABLE_DISCOVERY`.
For each pair in the table:
    A queue item is created with:
        slug
        date_since last metrics harvested
        date_to (daily close) to harvested data. This is the right end point of the interval
"""


def primer(event, context):
    # Scan the dynamo table for pairs and last_udpated
    # Create SQS Items for each of the pairs
    pass
