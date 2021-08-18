"""
executor.py
executor is trigger by SQS Items. Each item contains a slug and date range. Desired
metrics are harvested from Santiment over the date range. Once complete, an SNS message
is published showing data are complete
"""


def executor(event, context):
    pass
