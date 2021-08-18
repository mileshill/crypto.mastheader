import datetime
import http
import json
import os
from typing import Dict, List

import pandas as pd
import requests
import san

from internal.service_dynamo.dynamo import ServiceDynamo
from internal.service_sns.sns import ServiceSNS
from internal.service_ses.ses import ServiceSES, Email

DYNAMO = ServiceDynamo()
SNS = ServiceSNS()
SES = ServiceSES()


def load_env_vars(vars_required: List[str]) -> Dict[str, str]:
    """
    Loads required env vars
    :return:
        dict of string or error
    """
    # Load
    return {
        var: os.getenv(var)
        for var in vars_required
    }


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

    :param event:
    :param context:
    :return:
        None or Error
    """
    vars_required = ["KUCOIN_URL_ALLTICKERS", "SANTIMENT_KEY", "TABLE_DISCOVERY", "SNS_TOPIC_DISCOVERY"]
    vars_loaded = load_env_vars(vars_required)
    santiment_init(vars_loaded["SANTIMENT_KEY"])

    # Check for empty vars; return an error if exists
    for var, val in vars_loaded.items():
        # Handle empty env var
        if val == "" or val is None:
            return {
                "statusCode": http.HTTPStatus.BAD_REQUEST,
                "body": json.dumps({
                    "message": f"Missing ENV Var: {var}  Value: {val}"
                })
            }

    # Handle bad response from Kucoin
    response = requests.get(vars_loaded["KUCOIN_URL_ALLTICKERS"])
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

    # Update the Discovery table with non existent pairs
    new_slugs = list()
    for row in data.to_dict(orient="records"):
        td = vars_loaded["TABLE_DISCOVERY"]
        if not DYNAMO.key_exists(
                td,
                hash_key_name="slug", hash_key_value=row["slug"], hash_key_type="S"
        ):
            DYNAMO.discovery_create_item(td, row)
            new_slugs.append(row["slug"])

    # Publish the data to SNS
    current_utc_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    sns_message = {
        "subject": f"Mastheader: Discovery Process Complete {current_utc_time}",
        "message": f"Mastheader Discovery process complete. Discovered {len(new_slugs)} slugs.\n{','.join(new_slugs)}",
    }
    message_id = SNS.send_message(vars_loaded["SNS_TOPIC_DISCOVERY"], sns_message)

    return {
        "statusCode": http.HTTPStatus.OK,
        "body": json.dumps({
            "message": "Discovery complete successfully",
            "num_discovered": len(new_slugs),
            "slugs": ", ".join(new_slugs),
            "sns_topic": vars_loaded["SNS_TOPIC_DISCOVERY"],
            "sns_message_id": message_id
        })
    }


def notify(event, context):
    vars_required = ["SES_SENDER", "SES_RECIPIENT"]
    vars_loaded = load_env_vars(vars_required)

    for record in event["Records"]:
        email = Email(
            sender=vars_loaded["SES_SENDER"],
            recipient=vars_loaded["SES_RECIPIENT"],
            config_set="ConfigSet",
            subject=record["Sns"]["Subject"],
            message=record["Sns"]["Message"]
        )
        message_id = SES.send_email(email)
        print("SES Message ID: ", message_id)

