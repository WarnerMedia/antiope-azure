import json
import os
import time
import logging
import datetime
from dateutil import tz
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeDeserializer
from common import *


# Setup Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


## About this function:
# DyanmoDB Streams send a very DDB specific format to the stream target. While we typically thing of a DDB record as json, it is not.
# It's a funky format. The deseralize() function call will convert the DDB format into json which is then sent along to the final SNS topic
# that is the SNS topic that other tools can subscribe to.

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))

    try:
        for record in event['Records']:
            if record['eventSource'] != "aws:dynamodb":
                next

            # since this is only about newly discovered subscriptions, we only care about INSERT
            if record['eventName'] == "INSERT":
                ddb_record = record['dynamodb']['NewImage']
                if 'SubscriptionClass' in ddb_record:
                    del ddb_record['SubscriptionClass']
                logger.debug(ddb_record)
                json_record = deseralize(ddb_record)
                send_message(json_record, os.environ['ACTIVE_TOPIC'])

    except ClientError as e:
        logger.critical(f"ClientError - {e}")
        capture_error(event, context, e, f"ClientError - {e}")
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, event, vars(context)))
        capture_error(event, context, e, f"General Exception - {e}")
        raise


def send_message(record, topic):
    print("Sending Message: {}".format(record))
    sns_client = boto3.client('sns')
    try:
        sns_client.publish(
            TopicArn=topic,
            Subject="New Azure Subscription",
            Message=json.dumps(record, sort_keys=True, default=str),
        )
    except ClientError as e:
        logger.error('Error publishing message: {}'.format(e))


def deseralize(ddb_record):
    # This is probablt a semi-dangerous hack.
    # https://github.com/boto/boto3/blob/e353ecc219497438b955781988ce7f5cf7efae25/boto3/dynamodb/types.py#L233
    ds = TypeDeserializer()
    output = {}
    for k, v in ddb_record.items():
        output[k] = ds.deserialize(v)
    return(output)
