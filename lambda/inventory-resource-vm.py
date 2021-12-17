#!/usr/bin/env python3
"""
inventory-resource.py - an attempt at a generic extractor of known resources from Azure
given an array or (known) resource name will extract those resources from our Azure Enterprise
"""
import msal
import requests
import os
import json
import datetime
import logging

from dictor import dictor
from resourceloader import resourceloader
from resourcewriter import resourcewriter
from awssecret import get_secret
from awsevents import AWSevent
from cloudguard import CloudGuard
from azureresources import resourceEndpoints

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

#
# Limit the extraction of resources to only those subscriptions that have been 
# onboarded to CloudGurard.
#
# retrieve the cloudguard onboarded accounts
# fetch cloudguard secret once 
cg_secret_name = os.getenv('CLOUDGUARD_SECRET', default=None )
if cg_secret_name:
    cloudguard_creds = get_secret( cg_secret_name ) 
    
    cg = CloudGuard( creds=cloudguard_creds )
    if cg.error is not False:
        logger.error( f'GetAzureSubs received response {cg.error["status_code"]}.  Unable to get Azure Subs.' )
        cg_azure_subs = []
    else:
        cg_azure_subs = cg.AzureSubsHash.keys()

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

    inventory_bucket = os.environ["INVENTORY_BUCKET"]

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
        resource_endpoints = resourceEndpoints()
        #resources_to_capture = resource_endpoints.getKnownResources(excludes=['sqldb']) # sqldb is broken and vminstance is handled by inventory-vms.py lambda
        resources_to_capture = ["vminstance"]
        resource_counts = {}
        for tenant in SubsByTenantHash:
            # authenticate into the 0th subscription using the subscription_id, tenant_id and key values
            authentication_endpoint = 'https://login.microsoftonline.com/'
            resource_endpoint  = 'https://management.core.windows.net/'
            scopes = [ "https://management.core.windows.net//.default" ]
            app = msal.ConfidentialClientApplication(tenant_secrets[tenant]["application_id"], tenant_secrets[tenant][ "key" ], authority=f'{authentication_endpoint}{tenant_secrets[tenant][ "tenant_id" ]}')
            app_token = app.acquire_token_for_client( scopes ).get( "access_token")
            headers = {"Authorization": 'Bearer ' + app_token}
            for sub in SubsByTenantHash[ tenant ]:
                # Limit to only those subscriptions onboarded to CloudGuard
                # if sub["subscription_id"] not in cg_azure_subs:
                #     continue
                logger.debug(f'Beginning resource capture for {tenant} {sub["display_name"]} {sub["subscription_id"]}.  Resources {resources_to_capture}')
                nics_endpoint = resource_endpoints.getResourceEndpoint( 'networkinterface', sub["subscription_id"] )
                sub_nics = []
                while nics_endpoint:
                    nics_response = requests.get(nics_endpoint,headers=headers).json()
                    sub_nics.extend( nics_response["value"] )
                    if "nextLink" in nics_response:
                        nics_endpoint = nics_response["nextLink"]
                    else:
                        nics_endpoint = None
                nics_hash_by_vmid = mk_nics_hash_by_vmid( sub_nics )

                for resource in resources_to_capture:
                    resource_endpoint = resource_endpoints.getResourceEndpoint( resource, sub["subscription_id"] )
                    while resource_endpoint:
                        resource_json_output = requests.get(resource_endpoint,headers=headers).json()
                        if len( resource_json_output["value"] ) < 1:
                            break
                        s3prefix = f'Azure_Resources/{resource_endpoints.getS3Prefix(resource)}'
                        for item in resource_json_output["value"]:
                            item_name = item["id"].split("/")[-1]
                            if item["id"] in nics_hash_by_vmid:
                                supconfig = { "NetworkInterfaces": nics_hash_by_vmid[item["id"]] }
                                print("adding supp config")
                            else:
                                supconfig = {}
                            antiope_resource = mapAzureReourceToAntiopeResource( item, 
                                                                resource_endpoints.getAntiopeResourceType( resource ), 
                                                                subscription_id=sub["subscription_id"], 
                                                                sub_display_name=sub["display_name"],
                                                                tenant_id=tenant_secrets[tenant]["tenant_id"],
                                                                tenant_name=tenant,
                                                                supplementaryConfiguration=supconfig
                                                                )
                            if os.getenv( 'AWS_EXECUTION_ENV' ):
                                resourcewriter( dst=f's3://{inventory_bucket}/{s3prefix}/{item_name}.json', verbosity=False).writedata( json.dumps(antiope_resource, indent=2))
                            else: # assume we are testing locally 
                                os.makedirs( f'{inventory_bucket}/{s3prefix}', exist_ok=True )
                                resourcewriter( dst=f'file://{inventory_bucket}/{s3prefix}/{item_name}.json', verbosity=True).writedata( json.dumps(antiope_resource, indent=2))
                            if sub["subscription_id"] not in resource_counts:
                                resource_counts[sub["subscription_id"]] = 0
                            resource_counts[sub["subscription_id"]] += 1

                        if "nextLink" in resource_json_output:
                            resource_endpoint = resource_json_output[ "nextLink" ]
                        else:
                            resource_endpoint = None
                                                       
            for sub_id in resource_counts:
                logger.info( f'{resource_counts[sub_id]} reources for {sub_id} {AzureSubsHash[sub_id]["display_name"]} written.')


def mk_nics_hash_by_vmid(nics):
    hash = {}
    for nic in nics:
        vmid = dictor( nic, "properties.virtualMachine.id" ) 
        if vmid:
            if vmid not in hash:
                hash[vmid] = []
            hash[vmid].append( nic )
    return hash 


def getAzureRegion(azure_resource_object):
    if "location" in azure_resource_object:
        return( azure_resource_object["location"].replace( " ", "").lower() )
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

    if kwargs:
        resource_item.update( **kwargs )

    return( resource_item )



