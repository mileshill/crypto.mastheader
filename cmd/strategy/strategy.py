"""
strategy.py
Triggered from an SQS event, load the relevent metrics from Dynamo and evaluate for
a trade action. If a trade action should be made, publish to an SNS topic, else, do nothing
"""
import datetime
from typing import List, Dict

import pandas as pd

from internal.config.config import HarvestConfig
from internal.service_dynamo.dynamo import ServiceDynamo

HC = HarvestConfig()
DYNAMO = ServiceDynamo()


def get_sma_lookback_date(datetime_last_updated: str, lookback: int) -> str:
    dt_last_updated = datetime.datetime.strptime(datetime_last_updated, HC.time_format)
    dt_lookback = dt_last_updated - datetime.timedelta(days=lookback)
    return dt_lookback.strftime(HC.time_format)


def convert_items_to_dataframe(items: List[Dict]) -> pd.DataFrame:
    records = list()
    for item in items:
        new_record = {}
        for column in list(item.keys()):
            for v in item[column].values():
                new_record[column] = v
        records.append(new_record)
    return pd.DataFrame(records)


def strategy(event, context):
    for record in event["Records"]:
        slug = record["body"]
        ticker = record["messageAttributes"]["ticker"]["stringValue"]
        date_to = record["messageAttributes"]["datetime_last_updated"]["stringValue"]
        date_from = get_sma_lookback_date(date_to, HC.sma_lookback)

        # TODO
        # 1. Load data for the given slug between the datetime_last_update and datetime_lookback
        items = DYNAMO.harvest_get_data_for_slug_within_range(HC.table_harvest, slug, date_from, date_to)
        if items is None:
            print(f"NO DATA - Table {HC.table_harvest}, Slug {slug}, DateFrom {date_from}, DateTo: {date_to}")
            return

        # 2. Convert items list to dataframe. Implement the trade action decision pattern
        df = convert_items_to_dataframe(items)
        # 3. Publish any actions to SNS for multiple subscribers to execute
