#!/usr/bin/env python3
"""
inventory-resource.py - an attempt at a generic extractor of known resources from Azure
given an array or (known) resource name will extract those resources from our Azure Enterprise
"""
import adal
import requests
import os
import json
import datetime
import logging

from resourceloader import resourceloader
from awssecret import get_secret
from awsevents import AWSevent
from awselasticsearch import AwsElasticSearch

# set up logging
logger = logging.getLogger()
for name in logging.Logger.manager.loggerDict.keys():
    if ('boto' in name) or ('urllib3' in name) or ('s3transfer' in name) or ('boto3' in name) or ('botocore' in name) or ('nose' in name):
        logging.getLogger(name).setLevel(logging.WARNING)
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.basicConfig()


# load the Azure Subs table
antipe_azure_subs = resourceloader(f'ddb://{os.environ["SUBSCRIPTION_TABLE"]}').getdata()
AzureSubsHash = { sub["subscription_id"]:sub for sub in antipe_azure_subs }

# load the Azure Tenants Secret
tenant_secrets = get_secret( os.environ["AZURE_SECRET_NAME"] )


def handler(event, context):

    # manipulate logging messages in the lambda env so we get a run id on every message
    if os.getenv( 'AWS_EXECUTION_ENV' ):
        ch = logging.StreamHandler()
        formatter = logging.Formatter(f'{context.aws_request_id} [%(levelname)s] %(message)s')
        ch.setFormatter(formatter)
        logger.handlers = []
        logger.addHandler(ch)
    
    # put the event out in the logs
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))

    # we're only interested in the sns events
    evt = AWSevent( event )
    if "sns" not in evt.events:
        logger.info( f'No sns records found within event: {event}')
        return( event )

    # we should only have a single record in the event but can't guarantee so we are processing all sns records
    for record in evt.events["sns"]:
        # sort the subs to be scanned by tenant reducsing authentcation requests
        SubsByTenantHash = {}
        for sub in record['subscription_id']:
            if sub not in AzureSubsHash:
                logger.warn( "{sub} not found in subscriptions ddb data.")
            else:
                if AzureSubsHash[sub]["tenant_name"] not in SubsByTenantHash:
                    SubsByTenantHash[ AzureSubsHash[sub]["tenant_name"] ] = []
                SubsByTenantHash[ AzureSubsHash[sub]["tenant_name"] ].append( AzureSubsHash[sub] )

        # alocate the resource endpoints object
        resource_endpoints = resourceEndponts()
        resources_to_capture = resource_endpoints.getKnownResources()

        for tenant in SubsByTenantHash:
            # authenticate into the 0th subscription using the subscription_id, tenant_id and key values
            authentication_endpoint = 'https://login.microsoftonline.com/'
            resource_endpoint  = 'https://management.core.windows.net/'
            print( tenant_secrets[tenant][ "tenant_id" ] )
            auth_context = adal.AuthenticationContext(authentication_endpoint + tenant_secrets[tenant][ "tenant_id" ])
            print( SubsByTenantHash[ AzureSubsHash[sub]["tenant_name"] ][0]["subscription_id"] + ' : ' + tenant_secrets[tenant][ "key" ] )
            auth_response = auth_context.acquire_token_with_client_credentials(resource_endpoint, tenant_secrets[tenant]["application_id"], tenant_secrets[tenant][ "key" ] )
            access_token = auth_response.get('accessToken')
            headers = {"Authorization": 'Bearer ' + access_token}
            for sub in SubsByTenantHash[ AzureSubsHash[sub]["tenant_name"] ]:
                for resource in resources_to_capture:
                    resource_endpoint = resource_endpoints.getResourceEndpoint( resource, sub["subscription_id"] )
                    resource_json_output = requests.get(resource_endpoint,headers=headers).json()
                    print(sub["display_name"] + ': ' + sub["subscription_id"] + ' -- ' + resource )
                    if len( resource_json_output["value"] ) < 1:
                        continue
                    os.makedirs(f'json/{sub["subscription_id"]}/{resource}', exist_ok=True)
                    for item in resource_json_output["value"]:
                        item_name = item["id"].split("/")[-1]
                        with open(f'json/{sub["subscription_id"]}/{resource}/{item_name}.json', 'w') as outfile:
                            antiope_resource = mapAzureReourceToAntiopeResource( item, 
                                                                resource_endpoints.getAntiopeResourceType( resource ), 
                                                                subscription_id=sub["subscription_id"], 
                                                                sub_display_name=sub["display_name"],
                                                                tenant_id=tenant_secrets[tenant]["tenant_id"],
                                                                tenant_name=tenant 
                                                                )
                            json.dump(antiope_resource, outfile, indent=2)
                        print( f'     {item["id"].split("/")[-1]}')
                

class resourceEndponts():
    def __init__(self):
        self.azure_management_endpoint = "https://management.azure.com"
        self.excludes = ['sqldb', 'vminstance']
        self.res = {
            "akscluster": {
                "path": 'providers/Microsoft.ContainerService/managedClusters?api-version=2021-07-01',
                "azcli": "az aks list",
                "s3prefix": "aks/managedclusters",
                "a_res_type": "Compute::AksCluster"
                },
            "applicationgateway": {
                "path": 'providers/Microsoft.Network/applicationGateways?api-version=2021-03-01',
                "azcli": "az network application-gateway list",
                "s3prefix": "network/applicationgateway",
                "a_res_type": "Network::ApplicationGateway"
                },
            "bastion": {
                "path": 'providers/Microsoft.Network/bastionHosts?api-version=2021-03-01',
                "azcli": "az network bastion list",
                "s3prefix": "network/bastion",
                "a_res_type": "Network::Bastion"
                },
            "containerregistry": {
                "path": 'providers/Microsoft.ContainerRegistry/registries?api-version=2021-06-01-preview',
                "azcli": "az acr list",
                "s3prefix": "acr/containerregistry",
                "a_res_type": "ACR::ContainerRegistry"
                },
            "functionapp": {
                "path": 'providers/Microsoft.Web/sites?api-version=2020-09-01',
                "azcli": "az functionapp list",
                "s3prefix": "functions/app",
                "a_res_type": "FunctionApp"
            },
            "hdinsight": {
                "path": 'providers/Microsoft.HDInsight/clusters?api-version=2021-06-01',
                "azcli": "az hdinsight list",
                "s3prefix": "hdinsight/cluster",
                "a_res_type": "HDInsight"
                },
            "keyvault": {
                "path": 'resources?$filter=resourceType%20eq%20%27Microsoft.KeyVault%2Fvaults%27&api-version=2015-11-01',
                "azcli": "az keyvault list",
                "s3prefix": "keyvault",
                "a_res_type": "KeyVault"
                },
            "nsg": {
                "path": 'providers/Microsoft.Network/networkSecurityGroups?api-version=2021-03-01',
                "azcli": "az network nsg list",
                "s3prefix": "network/nsg",
                "a_res_type": "NetworkSecurityGroup"
                },
            "rediscache": {
                "path": 'providers/Microsoft.Cache/redis?api-version=2020-12-01',
                "azcli": "az redis list",
                "s3prefix": "redis/cluster",
                "a_res_type": "RedisCache"
                },
            "sqlserver": {
                "path": 'providers/Microsoft.SqlVirtualMachine/sqlVirtualMachines?api-version=2017-03-01-preview',
                "azcli": "az sql vm list",
                "s3prefix": "sql/vm",
                "a_res_type": "SQLServer"
                },
            "sqldb": {
                "comment": "requires sqlserver info like id, resourcegroup and server so must be a subsiquent call to 'sqlserver' call - seems broken in cli so won't work here",
                "path": 'providers/Microsoft.SqlVirtualMachine/sqlVirtualMachines?api-version=2017-03-01-preview',
                "azcli": "az sql db list",
                "s3prefix": "sql/db",
                "a_res_type": "SQLDB"
                },
            "storageaccount": {
                "path": 'providers/Microsoft.Storage/storageAccounts?api-version=2021-06-01',
                "azcli": "az storage account list",
                "s3prefix": "storage/account",
                "a_res_type": "Storage::StorageAccount"
                },
            "vminstance": {
                "comment": "listing vms appears to be a multi rest call effort.  will have to circle back",
                "path": 'providers/Microsoft.Compute/virtualMachines?api-version=2021-07-01',
                "azcli": "az vm list",
                "s3prefix": "vm/instance",
                "a_res_type": "VMSSInstance"
                },
            "vnet": {
                "path": 'providers/Microsoft.Network/virtualNetworks?api-version=2021-03-01',
                "azcli": "az network vnet list",
                "s3prefix": "network/vnet",
                "a_res_type": "Network::VNet"
                }
        }
    def getAntiopeResourceType(self, resource):
        return( self.res[resource]["a_res_type"] )

    def getResourceEndpoint(self, resource, subscription ):
        return( f'{self.azure_management_endpoint}/subscriptions/{subscription}/{self.res[resource]["path"]}' )

    def getKnownResources(self):
        return( set( self.res.keys() ) - set( self.excludes) )

def getAzureRegion(azure_resource_object):
    if "location" in azure_resource_object:
        return( azure_resource_object["location"] )
    return( "unknown")

def mapAzureReourceToAntiopeResource(azure_resource_object, antiope_resource_type, **kwargs):
    resource_item = {}
    resource_item['azureSubscriptionId']            = kwargs[ "subscription_id" ]
    resource_item['azureSubscriptionName']          = kwargs[ "sub_display_name" ]
    resource_item['azureTenantId']                  = kwargs[ "tenant_id" ]
    resource_item['azureTenantName']                = kwargs[ "tenant_name" ]
    resource_item['resourceType']                   = f'Azure::{antiope_resource_type}'
    resource_item['source']                         = "Antiope"
    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['configuration']                  = azure_resource_object
    resource_item['supplementaryConfiguration']     = {}
    resource_item['azureRegion']                    = getAzureRegion(azure_resource_object)
    resource_item['resourceId']                     = azure_resource_object["id"]
    resource_item['resourceCreationTime']           = "unknown"
    resource_item['errors']                         = {}
    return( resource_item )



# client_id="03e684f8-9051-4f8b-8fb2-f9e1a817a542"
# client_secret="e4Kl-_aNIU4MKhQQ7F@I/NakuUc51xbQ"
# tenant_id="0eb48825-e871-4459-bc72-d0ecd68f1f39"

# authentication_endpoint = 'https://login.microsoftonline.com/'
# resource  = 'https://management.core.windows.net/'

# # get an Azure access token using the adal library
# context = adal.AuthenticationContext(authentication_endpoint + tenant_id)
# token_response = context.acquire_token_with_client_credentials(resource, client_id, client_secret)

# access_token = token_response.get('accessToken')

# subscriptions_endpoint = 'https://management.azure.com/subscriptions/?api-version=2015-01-01'

# headers = {"Authorization": 'Bearer ' + access_token}
# json_output = requests.get(subscriptions_endpoint,headers=headers).json()
# resource_endpoints = resourceEndponts()
# resources = resource_endpoints.getKnownResources()

# for sub in json_output["value"]:
#     #print(sub["displayName"] + ': ' + sub["subscriptionId"])
#     for resource in resources:
#         resource_endpoint = resource_endpoints.getResourceEndpoint( resource, sub["subscriptionId"] )
#         resource_json_output = requests.get(resource_endpoint,headers=headers).json()
#         print(sub["displayName"] + ': ' + sub["subscriptionId"] + ' -- ' + resource )
#         if len( resource_json_output["value"] ) < 1:
#             continue
#         os.makedirs(f'json/{sub["subscriptionId"]}/{resource}', exist_ok=True)
#         for item in resource_json_output["value"]:
#             item_name = item["id"].split("/")[-1]
#             with open(f'json/{sub["subscriptionId"]}/{resource}/{item_name}.json', 'w') as outfile:
#                 antiope_resource = mapAzureReourceToAntiopeResource( item, 
#                                                     resource_endpoints.getAntiopeResourceType( resource ), 
#                                                     subscription_id=sub["subscriptionId"], 
#                                                     sub_display_name=sub["displayName"],
#                                                     tenant_id=tenant_id,
#                                                     tenant_name='turner' 
#                                                     )
#                 json.dump(antiope_resource, outfile, indent=2)
#             print( f'     {item["id"].split("/")[-1]}')
