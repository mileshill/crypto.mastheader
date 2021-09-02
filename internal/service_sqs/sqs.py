"""
sqs.py
"""
import boto3
from typing import Dict, List


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

    def send_in_batches(self, messages: List[Dict]) -> None:
        max_batch_size = 10
        for i in range(0, len(messages), max_batch_size):
            batch = messages[i: i + max_batch_size]
            self.client.send_message_batch(
                QueueUrl=self.queue_url,
                Entries=batch
            )
        return

    def delete_message(self, receipt_handle: str):
        self.client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle
        )
