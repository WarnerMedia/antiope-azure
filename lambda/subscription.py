import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import os
import logging
import datetime
from dateutil import tz
from pprint import pprint

from msrestazure.azure_active_directory import ServicePrincipalCredentials
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.storage import StorageManagementClient
#from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.sql import SqlManagementClient
#from azure.mgmt.datafactory import DataFactoryManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
#from azure.mgmt.logic import LogicManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resourcegraph import ResourceGraphClient

# Setup Logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


class AntiopeAzureSubscription(object):
    """Class to represent a Azure Subscription """
    def __init__(self, subscription_id):
        '''
            Takes a subsription as the lookup attribute
        '''
        # Execute any parent class init()

        self.subscription_id = subscription_id
        
        # Save these as attributes
        self.credentials = ""
        self.dynamodb = boto3.resource('dynamodb')
        self.subscription_table = self.dynamodb.Table(os.environ['SUBSCRIPTION_TABLE'])

        response = self.subscription_table.query(
            KeyConditionExpression=Key('subscription_id').eq(self.subscription_id),
            Select='ALL_ATTRIBUTES'
        )
        try:
            self.db_record = response['Items'][0]
            # Convert the response into instance attributes
            self.__dict__.update(self.db_record)
        except IndexError as e:
            raise SubscriptionLookupError("ID {} not found".format(self.subscription_id))
        except Exception as e:
            logger.error("Got Other error: {}".format(e))

    def __str__(self):
        """when converted to a string, become the subscription_id"""
        return(self.subscription_id)

    def __repr__(self):
        '''Create a useful string for this class if referenced'''
        return("<Antiope.AntiopeAzureSubscription {} >".format(self.subscription_id))


#
# Database functions
#

    def update_attribute(self, table_name, key, value):
        '''    update a specific attribute in a specific table for this subscription
            table_name should be a valid DynDB table, key is the column, value is the new value to set
        '''
        logger.info(u"Adding key:{} value:{} to subscription {}".format(key, value, self))
        table = self.dynamodb.Table(table_name)
        try:
            response = table.update_item(
                Key= {
                    'subscription_id': self.subscription_id
                },
                UpdateExpression="set #k = :r",
                ExpressionAttributeNames={
                    '#k': key
                },
                ExpressionAttributeValues={
                ':r': value,
                }
            )
        except ClientError as e:
            raise SubscriptionUpdateError("Failed to update {} to {} in {}: {}".format(key, value, table_name, e))

    def get_attribute(self, table_name, key):
        '''
        Pulls a attribute from the specificed table for the subscription
        '''
        logger.info(u"Getting key:{} from:{} for subscription {}".format(key, table_name, self))
        table = self.dynamodb.Table(table_name)
        try:
            response = table.get_item(
                Key= {
                    'subscription_id': self.subscription_id
                },
                AttributesToGet=[ key ]
            )
            return(response['Item'][key])
        except ClientError as e:
            raise SubscriptionLookupError("Failed to get {} from {} in {}: {}".format(key, table_name, self, e))
        except KeyError as e:
            raise SubscriptionLookupError("Failed to get {} from {} in {}: {}".format(key, table_name, self, e))

    def delete_attribute(self, table_name, key):
        '''
        Pulls a attribute from the specificed table for the subscription
        '''
        logger.info(u"Deleting key:{} from:{} for subscription {}".format(key, table_name, self))
        table = self.dynamodb.Table(table_name)
        try:
            response = table.update_item(
                Key= {
                    'subscription_id': self.subscription_id
                },
                UpdateExpression="remove #k",
                ExpressionAttributeNames={
                    '#k': key
                },
                # ExpressionAttributeValues={
                # ':r': value,
                # }
            )
        except ClientError as e:
            raise SubscriptionLookupError("Failed to get {} from {} in {}: {}".format(key, table_name, self, e))
        except KeyError as e:
            raise SubscriptionLookupError("Failed to get {} from {} in {}: {}".format(key, table_name, self, e))


#
# ARM Methods
#

    def authenticate(self, secret_name):
        """
        Get the azure service account key stored in AWS secrets manager.
        """

        client = boto3.client('secretsmanager')
        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        except ClientError as e:
            logger.error("Unable to get secret value for {}: {}".format(secret_name, e))
            raise ServicePrincipalError(e)
        else:
            if 'SecretString' in get_secret_value_response:
                secret_value = get_secret_value_response['SecretString']
            else:
                secret_value = get_secret_value_response['SecretBinary']

        try:
            secret_dict = json.loads(secret_value)
            if self.tenant_name in secret_dict:
                creds = secret_dict[self.tenant_name]
        except Exception as e:
            logger.error("Error during Credential and Service extraction: {}".format(e))
            raise ServicePrincipalError(e)

        try:
            self.credentials = ServicePrincipalCredentials(
                client_id=creds['application_id'],
                secret=creds['key'],
                tenant=creds['tenant_id']
            )
        except Exception as e:
            raise ServicePrincipalError(e)


    def get_client(self, client_type):
        """
        Return resource management client type based on what's requested
        """
        
        try:
            # Check to see if credentials exist before returning an azure client object
            if self.credentials:
                # there is probably a better whay than a big case statement
                if client_type == "ComputeManagementClient":
                    return(ComputeManagementClient(self.credentials, self.subscription_id))
                elif client_type == "ResourceGraphClient":
                    return(ResourceGraphClient(self.credentials, base_url=None))
                else:
                    raise NotImplementedError("No such client type {} supported".format(client_type))
            else:
                raise ServicePrincipalError("Missing or bad credentials for tenant {}".format(self.tenant_name))
        
        except ServicePrincipalError as e:
            raise(e)
        except NotImplementedError as e:
            raise(e)
        except Exception as e:
            raise(e)
  

class ServicePrincipalError(Exception):
    # Raised when the AssumeRole Fails
    pass

class SubscriptionUpdateError(Exception):
    # Raised when an update to DynamoDB Fails
    pass

class SubscriptionLookupError(LookupError):
    # Raised when the Subscription requested is not in the database 
    pass
    
class NotImplementedError(Exception):
    # Raised when there is missing configuration 
    pass

class ClientError(Exception):
    # Raised when there are client exceptions
    pass
