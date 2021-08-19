import boto3
from typing import Dict

class ServiceSNS:
    def __init__(self):
        self.client = boto3.client("sns")

    def send_message(self, topic: str, message: Dict[str, str]) -> str:
        topic_arn = None
        existing_topics = self.client.list_topics()

        # Find existing topic ARN
        for t in existing_topics["Topics"]:
            t_arn = t["TopicArn"]
            topic_name = t_arn.split(":")[-1]
            if topic_name == topic:
                topic_arn = t_arn

        # If ARN is not found, create it
        if topic_arn is None:
            response = self.client.create_topic(Name=topic)
            topic_arn = response["TopicArn"]

        # Publish the message
        message["TopicArn"] = topic_arn
        response = self.client.publish(**message)
        return response["MessageId"]


