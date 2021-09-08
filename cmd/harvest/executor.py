"""
executor.py
executor is trigger by SQS Items. Each item contains a slug and date range. Desired
metrics are harvested from Santiment over the date range. Once complete, an SNS message
is published showing data are complete
"""
import datetime
import http
import json
import random
from typing import Dict

import pandas as pd
import san

from internal import HC, DYNAMO
from internal.service_sqs.sqs import ServiceSQS

SQSHarvest = ServiceSQS(HC.queue_harvest)
SQSStrategy = ServiceSQS(HC.queue_strategy)
san.ApiConfig.api_key = HC.santiment_key


def send_to_queue_for_reprocessing(record: Dict, delay_seconds: int) -> str:
    message = {
        "DelaySeconds": delay_seconds,
        "MessageBody": record["body"],
        "MessageAttributes": record["messageAttributes"]
    }
    message_id = SQSHarvest.send_message(message)
    return message_id


def executor(event, context):
    """
    executor is triggered by SQS events coming from the harvestPrimer. harvestPrimer is creating SQS messages that
    have the following attributes:
        1. MessageBody - slug
        2. MessageAttributes
            datetime_last_updated: value or "null"
            ticker: str

    :param event:
    :param context:
    :return:
    """
    # Metrics to collect
    santiment_metrics = [
        "price_usd", "marketcap_usd",
        "exchange_outflow_change_1d", "exchange_inflow_change_1d",
        "age_consumed",
        "active_addresses_24h_change_1d", 'volume_usd_change_1d', 'volume_usd'
    ]

    for record in event["Records"]:
        # Index for dynamo and santiment
        slug = record["body"]
        ticker = record["messageAttributes"]["ticker"]["stringValue"]

        # Handle cases where things have not yet been updated
        datetime_last_updated = record["messageAttributes"]["datetime_last_updated"]["stringValue"]
        if datetime_last_updated == "null":
            last_update = DYNAMO.harvest_get_last_update_for_slug(HC.table_harvest, slug)
            if last_update is not None:
                datetime_last_updated = last_update
            else:
                datetime_last_updated = (datetime.datetime.utcnow() - datetime.timedelta(days=60)).strftime("%Y-%m-%d")

        # Build the batch for each of the metrics
        batch = san.Batch()
        for metric in santiment_metrics:
            batch.get(
                f"{metric}/{slug}",
                from_date=datetime_last_updated
            )

        # Make the call. Handle rate-limiting
        try:
            results = batch.execute()
        except Exception as e:
            if san.is_rate_limit_exception(e):
                print(e)
                SQSHarvest.delete_message(record["receiptHandle"])
                print(f"Deleting record for slug: {slug}")
                # Rate limit and random backoff between 1 and 10 minutes
                delay_seconds = min(san.rate_limit_time_left(e) + random.randint(60, 600), 900)
                record["messageAttributes"]["datetime_last_updated"]["stringValue"] = datetime_last_updated
                message_id = send_to_queue_for_reprocessing(record, delay_seconds)
                print("Republished to SQS - MessageID: ", message_id)
            else:
                raise e

        # Rename the columns to metric names
        for df, col in zip(results, santiment_metrics):
            df.rename(columns={"value": col}, inplace=True)

        # Join the dataframes. If it is missing the two important metrics, it will be delete
        results = pd.concat(results, axis=1)
        if "price_usd" not in results.columns or "active_addresses_24h_change_1d" not in results.columns:
            print(f"Slug {slug} missing desire columns")
            print(f"Result after concat: \n{results}")
            print(f"Deleting {slug} from {HC.table_discovery}")
            DYNAMO.discovery_delete_item(HC.table_discovery, slug)

        # Drop empty records and get datetime back into the columns
        try:
            results = results.dropna(subset=["price_usd", "active_addresses_24h_change_1d"]).reset_index()
        except KeyError as e:
            DYNAMO.discovery_delete_item(HC.table_discovery, slug)
            print(f"Key Error: Deleting {slug} from {HC.table_discovery}")
            return
        results_last_datetime = results["datetime"].max()
        results["datetime_metric"] = results["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        results.drop(labels=["datetime"], axis=1, inplace=True)

        results["slug"] = slug
        results = results.astype(str)
        results = results.to_dict(orient="records")

        # Write everything to Dynamo
        for sample in results:
            item = DYNAMO.create_item_from_dict(sample)
            DYNAMO.harvest_create_item(HC.table_harvest, item)
        SQSHarvest.delete_message(record["receiptHandle"])

        # Publish to SQS
        message_id = SQSStrategy.send_message({
            "MessageBody": slug,
            "MessageAttributes": {
                "datetime_last_updated": {
                    "StringValue": results_last_datetime.strftime(HC.time_format),
                    "DataType": "String"
                },
                "ticker": {
                    "StringValue": ticker,
                    "DataType": "String"
                }
            }
        })
        print(f"Slug {slug} santiment scraped. Sent to next queue: {SQSStrategy.queue_name}")
        return {
            "statusCode": http.HTTPStatus.OK,
            "body": json.dumps({
                "message": f"Loaded data for {slug}",
                "message_id": message_id
            })
        }
