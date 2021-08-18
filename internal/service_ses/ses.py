import boto3
import botocore.exceptions


class Email:
    def __init__(self, sender, recipient, subject, message):
        self.sender = sender
        self.recipient = recipient
        self.subject = subject
        self.message = message


class ServiceSES:
    def __init__(self):
        self.client = boto3.client("ses")

    def send_email(self, email: Email):
        body_html = f"""<html>
            <head></head>
            <body> 
            <h3>{email.subject}</h3>
            <p>{email.message}</p>
            </body>
            </html>
            """
        body_text = email.message
        charset = "UTF-8"
        try:
            response = self.client.send_email(
                Source=email.sender,
                Destination={
                    "ToAddresses": [
                        email.recipient
                    ]
                },
                Message={
                    "Body": {
                        "Html": {
                            "Charset": charset,
                            "Data": body_html
                        },
                        "Text": {
                            "Charset": charset,
                            "Data": body_text
                        }
                    },
                    "Subject": {
                        "Charset": charset,
                        "Data": email.subject
                    }
                }
            )
        except botocore.exceptions.ClientError as e:
            print(e)
            return
        else:
            return response["MessageId"]
