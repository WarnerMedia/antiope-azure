import json
import os
import logging
import boto3
import time
import urllib3
from botocore.exceptions import ClientError
from subscription import AntiopeAzureSubscription
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.mgmt.resourcegraph.models import *


# Setup Logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('msrest').setLevel(logging.INFO)


#
# Common Functions
#

def graph_resource_query(gr_query, target_sub, management_client):

    # Retry Parameters
    retries = 3
    attempt = 1
    
    # Setup Query Request
    q = QueryRequest(
        query=gr_query,
        subscriptions=[target_sub.subscription_id],
        options=QueryRequestOptions(
            result_format=ResultFormat.object_array
            )
        )

    count = 0
    data = {}
    status = ''
    
    while attempt <= retries:
        
        logger.debug("Sending resource graph query for subscription {}({}), attempt: {} of {}".format(target_sub.display_name, target_sub.subscription_id, str(attempt), str(retries)))
        
        try:
            response = management_client.resources(q)
            data = response.data
            count = response.count
            status = '200'
            break
        
        except Exception as e:
            attempt +=1
            logger.error(f'API Call failed for subscription {target_sub.display_name}({target_sub.subscription_id}. {e})' )
            time.sleep(10)
            
            if attempt > retries:
                logger.error("API Call failed for subscription {}({}) after {} retries".format(target_sub.display_name, target_sub.subscription_id, str(retries)))
                status = '503'
            
            continue
    
    return count, status, data

def save_resource_to_s3(prefix, resource_id, resource):
    """
    This function saves a json file to s3
    :param prefix: like VM, APP-SERVICE
    :param resource_id: the id of the resource often Azure uses slashes \ but we turn them into -
    :param resource: the json of the resources
    :return: Nothing
    """
    s3client = boto3.client('s3')
    object_key = "Azure-Resources/{}/{}.json".format(prefix, resource_id)

    try:
        s3client.put_object(
            Body=json.dumps(resource, sort_keys=False, default=str, indent=2),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key=object_key,
        )
    except ClientError as e:
        logger.error("Unable to save object {}: {}".format(object_key, e))


def safe_dump_json(obj)->dict:
    """
    Converts an object to a json in a shallow way
    :param obj:
    :return:
    """
    # TODO needs to be able to parse json of json
    json_obj = {}
    for key in obj.__dict__.keys():
        json_obj[key] = str(obj.__dict__[key])

    return json_obj


def get_active_subscriptions(table_name=None):
    """Returns an array of all active azure subscriptions as AntiopeAzureSubscription objects"""
    sub_ids = get_subscription_ids(status="Enabled", table_name=table_name)
    output = []
    for sub_id in sub_ids:
        output.append(AntiopeAzureSubscription(sub_id))
    return(output)


def get_subscription_ids(status=None, table_name=None):
    """return an array of subscription_ids from the Subscriptions table. Optionally, filter by status"""
    dynamodb = boto3.resource('dynamodb')
    if table_name:
        subscription_table = dynamodb.Table(table_name)
    else:
        subscription_table = dynamodb.Table(os.environ['SUBSCRIPTION_TABLE'])

    subscription_list = []
    response = subscription_table.scan(
        AttributesToGet=['subscription_id', 'subscription_state']
    )
    while 'LastEvaluatedKey' in response:
        # Means that dynamoDB didn't return the full set, so ask for more.
        subscription_list = subscription_list + response['Items']
        response = subscription_table.scan(
            AttributesToGet=['subscription_id', 'subscription_state'],
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
    subscription_list = subscription_list + response['Items']
    output = []
    for a in subscription_list:
        if status is None:  # Then we get everything
            output.append(a['subscription_id'])
        elif a['subscription_state'] == status:  # this is what we asked for
            output.append(a['subscription_id'])
        # Otherwise, don't bother.
    return(output)


def get_subcriptions(azure_creds):

    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    resource_client = SubscriptionClient(creds)

    collected_subs = []
    for subscription in resource_client.subscriptions.list():

        consumption_client = ConsumptionManagementClient(creds, subscription.subscription_id, base_url=None)
        sum = 0
        for uu in consumption_client.usage_details.list():
            sum += uu.pretax_cost

        subscription_dict = {"subscription_id": subscription.subscription_id, "display_name": subscription.display_name,
                             "cost": int(sum), "state": str(subscription.state)}


        collected_subs.append(subscription_dict)

    return collected_subs


def get_azure_creds(secret_name):
    """
    Get the azure service account key stored in AWS secrets manager.
    """

    client = boto3.client('secretsmanager')
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logger.error(f"Unable to get secret value for {secret_name}: {e}")
        return(None)
    else:
        if 'SecretString' in get_secret_value_response:
            secret_value = get_secret_value_response['SecretString']
        else:
            secret_value = get_secret_value_response['SecretBinary']

    try:
        secret_dict = json.loads(secret_value)
        return secret_dict
    except Exception as e:
        logger.error(f"Error during Credential and Service extraction: {e}")
        return(None)


#
# Error Handling Functions
#

def capture_error(event, context, error, message):
    '''When an exception is thrown, this function will publish a SQS message for later retrival'''
    sqs_client = boto3.client('sqs')

    queue_url = os.environ['ERROR_QUEUE']

    body = {
        'event': str(event),
        'function_name': context.function_name,
        'aws_request_id': context.aws_request_id,
        'log_group_name': context.log_group_name,
        'log_stream_name': context.log_stream_name,
        'error': str(error),
        'message': message
    }

    logger.info(f"Sending Lambda Exception Message: {body}")
    response = sqs_client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
    return(body)
