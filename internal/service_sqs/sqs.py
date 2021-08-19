"""
sqs.py
"""
import boto3
from typing import Dict


class ServiceSQS:
    def __init__(self, queue_name: str):
        self.client = boto3.client("sqs")
        self.queue_name = queue_name
        self.queue_url = self.get_queue_url(queue_name)

    def get_queue_url(self, queue_name: str):
        response = self.client.get_queue_url(
            QueueName=queue_name
        )
        return response["QueueUrl"]

    def send_message(self, payload: Dict):
        response = self.client.send_message(
            QueueUrl=self.queue_url,
            **payload
        )
        return response["MessageId"]

    def delete_message(self, receipt_handle: str):
        self.client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle
        )
