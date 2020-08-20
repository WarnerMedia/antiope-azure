import boto3
import json
import os
import logging
import time


# Setup Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


def handler(event, context):
    if 'debug' in event and event['debug']:
        logger.setLevel(logging.DEBUG)

    if 'DEBUG' in os.environ and os.environ['DEBUG'] == "True":
        logger.setLevel(logging.DEBUG)

    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    # Setup client
    client = boto3.client('sns')

    # In order to limit the number of lamba functions making API calls and exceeding the throttling limit
    # send a group of subscription ID's to SNS rather then each individual ID for each lamba function to process.
    subs = event['subscription_list']
    
    # Divide the list of subs into chunks
    sub_groups = list(divide_into_chunks(subs)) 
    
    # Cycle through each sub group and send to SNS
    for subscription_id in sub_groups:
    
        sns_delay = int(os.environ['SNS_DELAY'])
        message = {}
        message['subscription_id'] = subscription_id

        logger.info("Pushing Message: " + json.dumps(message, sort_keys=True))
    
        response = client.publish(
            TopicArn=os.environ['TRIGGER_ACCOUNT_INVENTORY_ARN'],
            Message=json.dumps(message)
        )
        
        if sns_delay != 0:
            logger.info("SNS delay is greater then zero, sleeping {} second(s)".format(str(sns_delay)))
            time.sleep(sns_delay)

    return event

def divide_into_chunks(subs): 
     
    # Number of subscription ID's grouped and sent to SNS 
    num = int(os.environ['NUM_SUBS_IN_GROUP'])
    
    # looping till length num
    for i in range(0, len(subs), num):  
        yield subs[i:i + num]

