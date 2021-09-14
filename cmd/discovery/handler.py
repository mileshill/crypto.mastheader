import datetime
import http
import json

import pandas as pd
import requests
import san

from internal import HC, DYNAMO, SNS, SES
from internal.service_ses.ses import Email


def santiment_init(key: str) -> None:
    """
    Set the api key on the global instance
    :param key: API key
    :return:
    """
    san.ApiConfig.api_key = key


def santiment_get_projects() -> pd.DataFrame:
    """
    Load all projects tracked by Santiment
    :return:
        Dataframe with columns:
            marketSegment: str
            name: str
            slug: str
            ticker: str
            totalSupply: float
    """
    return san.get("projects/all")


def discovery(event, context):
    """
    discovery locates new tokens in the intersection between KuCoin and Santiment.
    New pairs are uploaded to a DynamoDB table.
    The results a published to SNS where the `notify` function sends an SES email.
    :param event:
    :param context:
    :return:
        None or Error
    """
    santiment_init(HC.santiment_key)

    # Handle bad response from Kucoin
    response = requests.get(HC.kucoin_url_alltickers)
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        return {
            "statusCode": http.HTTPStatus.BAD_REQUEST,
            "body": json.dumps({
                "message": "Failed to query KuCoin.AllTickers API",
                "error": str(e)
            })
        }

    # Get the unique pairs. Drop the XXX-BTC, XXX-USDT -> XXX
    pairs = list(set((pair["symbol"].split("-")[0].upper() for pair in response.json()["data"]["ticker"])))
    kucoin_pairs = pd.DataFrame.from_dict({"ticker": pairs})

    # Get Santiment projects
    santiment_pairs = santiment_get_projects()

    # Inner join to get pairs supported by Santiment
    data = pd.merge(santiment_pairs, kucoin_pairs, how="inner", left_on="ticker", right_on="ticker")
    data["totalSupply"] = data["totalSupply"].fillna(0)
    data = data.astype(str)
    data = data[data["marketSegment"] != "Stablecoin"]



    # Update the Discovery table with non existent pairs
    bad_slugs = ["usd-coin", "susd", "tether"]
    new_slugs = list()
    for row in data.to_dict(orient="records"):
        if row["slug"] in bad_slugs:
            continue
        td = HC.table_discovery
        if not DYNAMO.key_exists(
                td,
                hash_key_name="slug", hash_key_value=row["slug"], hash_key_type="S"
        ):
            item = DYNAMO.create_item_from_dict(row)
            DYNAMO.discovery_create_item(td, item)
            new_slugs.append(row["slug"])

    # Publish the data to SNS
    current_utc_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    new_slugs.sort()
    new_slugs_formatted = ",\n".join(new_slugs)
    sns_message = {
        "Subject": f"Mastheader: Discovery Process Complete {current_utc_time}",
        "Message": f"Mastheader Discovery process complete. Discovered {len(new_slugs)} slugs.\n{new_slugs_formatted}",
    }
    message_id = SNS.send_message(HC.sns_topic_discovery, sns_message)

    return {
        "statusCode": http.HTTPStatus.OK,
        "body": json.dumps({
            "message": "Discovery complete successfully",
            "num_discovered": len(new_slugs),
            "slugs": ", ".join(new_slugs),
            "sns_topic": HC.sns_topic_discovery,
            "sns_message_id": message_id
        })
    }


def notify(event, context):
    """
    notify parses the SNS record from the discovery completions and sends an email
    to the SES_RECIPIENT
    :param event:
    :param context:
    :return:
    """

    for record in event["Records"]:
        email = Email(
            sender=HC.ses_sender,
            recipient=HC.ses_recipient,
            subject=record["Sns"]["Subject"],
            message=record["Sns"]["Message"]
        )
        message_id = SES.send_email(email)
        print("SES Message ID: ", message_id)
