import json
import os
import time
import datetime
import logging
import boto3
from botocore.exceptions import ClientError
from mako.template import Template
from subscription import *
from common import *

# Setup Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


# table_format = {
#   "cost": 38,
#   "display_name": "azure-account",
#   "state": "SubscriptionState.enabled",
#   "subscription_id": "01a61c45-4b7b-4569-9017-310d8e9ececd"
#   "tenant_name": "wb"
# }


table_format = ["display_name", "subscription_id", "tenant_name", "cost", "subscription_state" ]

# Lambda main routine
def handler(event, context):
    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    dynamodb = boto3.resource('dynamodb')
    account_table = dynamodb.Table(os.environ['SUBSCRIPTION_TABLE'])


    # We will make a HTML Table and a Json file with this data
    table_data = ""
    json_data = {'subscriptions': [] }

    # Get and then sort the list of subscriptions by name, case insensitive.
    subscription_list = get_active_subscriptions()
    subscription_list.sort(key=lambda x: x.display_name.lower())

    for subscription in subscription_list:
        logger.info(f"{subscription.subscription_id}")
        j = subscription.db_record.copy()
        j['cost'] = "NotImplemented"
        json_data['subscriptions'].append(j)


    json_data['timestamp'] = datetime.datetime.now()
    json_data['subscription_count'] = len(subscription_list)
    json_data['bucket'] = os.environ['INVENTORY_BUCKET']

    fh = open("html_templates/subscription_inventory.html", "r")
    mako_body = fh.read()
    result = Template(mako_body).render(**json_data)

    s3_client = boto3.client('s3')
    try:
        response = s3_client.put_object(
            # ACL='public-read',
            Body=result,
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='text/html',
            Key='Reports/azure_subscription_inventory.html',
        )

        # Save the JSON to S3
        response = s3_client.put_object(
            # ACL='public-read',
            Body=json.dumps(json_data, sort_keys=True, indent=2, default=str),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key='Reports/azure_subscription_inventory.json',
        )
    except ClientError as e:
        logger.error("ClientError saving report: {}".format(e))
        raise

    return(event)


