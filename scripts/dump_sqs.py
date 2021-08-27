"""
dump_sqs.py
Purge the SQS Queues for a given region and stage.
"""
import boto3
from collections import deque
from configargparse import ArgParser

parser = ArgParser(default_config_files=[], auto_env_var_prefix="")
parser.add_argument("--stage", type=str, required=True)
parser.add_argument("--region-name", type=str, default="ca-central-1")

if __name__ == "__main__":
    args = parser.parse_known_args()[0]
    client = boto3.client("sqs", region_name=args.region_name)

    # Generator of queues
    queues = (
        client.purge_queue(QueueUrl=queue)
        for queue in client.list_queues().get("QueueUrls")
        if args.stage in queue
    )

    # Consume the generator
    deque(queues, maxlen=0)
