import boto3
from botocore.exceptions import ClientError
import json
import os
import time
import logging
import datetime
from common import *
from subscription import *

# Setup Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)

def lambda_handler(event, context):
    logger.info("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    for sub in message['subscription_id']:
        
        try:
            # Create an antiope instance for this subscription
            target_sub = AntiopeAzureSubscription(sub)
        
            # Fetch the service principal info from Secrets Manager and authenticate
            target_sub.authenticate(os.environ['AZURE_SECRET_NAME'])
        
            # Management Client
            management_client = target_sub.get_client("ResourceGraphClient")
    
            # Query
            query = """Resources
                       | where type == 'microsoft.compute/virtualmachines'
                       | project id, properties
                    """
        
            # Call Resource Graph API
            vm_count, status, vm_list = graph_resource_query(query, target_sub, management_client)
    
            # Cycle through the list of virtual machines, extract information, and save as a json file to S3
            if status == '200' and vm_count > 0:
                logger.info("Subscription {} has {} virtual machines".format(target_sub.subscription_id, vm_count))
            
                for vm in vm_list:
                    process_instances(target_sub, vm, management_client)
            
            elif status=='200' and vm_count == 0:
                logger.info("No virtual machines found for subscription {}({}), skipping".format(target_sub.display_name,target_sub.subscription_id))
                
            else:
                logger.error("Error getting virtual machine information for subscription {}({}), exiting".format(target_sub.display_name, target_sub.subscription_id))
                raise ClientError(f"Error getting virtual machine information for subscription {target_sub.display_name}({target_sub.subscription_id})")
            
        except ServicePrincipalError as e:
            logger.error("Event: ServicePrincipalError, Context: {}, Error: {}, Subscription {}({})".format(vars(context), e, target_sub.display_name, target_sub.subscription_id))
            capture_error("ServicePrincipalError", context, e, "Subscription: {}({})".format(target_sub.display_name, target_sub.subscription_id))
    
        except ClientError as e:
            logger.error("Event: ClientError, Context: {}, Error: {}, Message: Subscription: {}({})".format(vars(context), e, target_sub.display_name, target_sub.subscription_id))
            capture_error("ClientError", context, e, "Subscription: {}({})".format(target_sub.display_name, target_sub.subscription_id))
    
        except NotImplementedError as e:
            logger.error("Event: NotImplementedError, Context: {}, Error: {}, Message: Subscription: {}({})".format(vars(context), e, target_sub.display_name, target_sub.subscription_id))
            capture_error("ClientError", context, e, "Subscription: {}({})".format(target_sub.display_name, target_sub.subscription_id))
    
        except Exception as e:
            logger.error("Event: General Exception, Context: {}, Error: {}, Message: Subscription: {}".format(vars(context), e, sub))
            capture_error("General Exception", context, e, "Subscription: {}".format(sub))


def process_instances(target_sub, vm, management_client):

    # Virtual Machine Resource and Machine ID
    id = vm['id']
    vmid = vm['properties']['vmId']
                    
    # Network Interface Details
    query = f"""Resources 
                | where type == 'microsoft.compute/virtualmachines' 
                | where id == '{id}' 
                | mvexpand nic = properties.networkProfile.networkInterfaces 
                | extend nicId = tostring(nic.id) 
                | project resourceGroup, properties, nicId 
                  | join kind=leftouter (Resources 
                    | where type == 'microsoft.network/networkinterfaces' 
                    | mvexpand ipconfig=properties.ipConfigurations 
                    | extend publicIpId = tostring(ipconfig.properties.publicIPAddress.id) 
                    | project nicId = id, resourceGroup, privateNetworkInterfaceName = name, privateNetworkProperties = properties, publicIpId
                    ) on nicId 
                  | join kind=leftouter (Resources 
                    | where type =~ 'microsoft.network/publicipaddresses' 
                    | project publicIpId = id, publicNetworkInterfaceName = name, publicNetworkProperties = properties, resourceGroup
                    ) on publicIpId 
                | project-away publicIpId1
                | project-away nicId1
                | project nicId, resourceGroup, privateNetworkInterfaceName, privateNetworkProperties, publicIpId, publicNetworkInterfaceName, publicNetworkProperties
            """
    
    # Call API
    logger.info("Processing subscription {}({}), virtual machine {}".format(target_sub.subscription_id, target_sub.display_name, vmid))
    count, status, vm_network = graph_resource_query(query, target_sub, management_client)
    
    if status == '200':
        # Build JSON Object
        resource_item = {}
        resource_item['azureSubscriptionId']            = target_sub.subscription_id
        resource_item['azureSubscriptionName']          = target_sub.display_name
        resource_item['azureTenantId']                  = target_sub.tenant_id
        resource_item['azureTenantName']                = target_sub.tenant_name
        resource_item['resourceType']                   = "Azure::Compute::VM"
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = vm
        resource_item['supplementaryConfiguration']     = {}
        resource_item['azureRegion']                    = "unknown"
        resource_item['resourceId']                     = vmid
        resource_item['resourceCreationTime']           = "unknown"
        resource_item['errors']                         = {}
        
        # Work around for API, sometimes on some subscriptions/virtual machines the location does not return a value.        
        if 'location' in vm: 
            resource_item['azureRegion']                = vm['location']
        
        # Set network info   
        if vm_network:
            resource_item['supplementaryConfiguration']['NetworkInterfaces'] = vm_network
                    
        # Save to S3
        logger.info("Writing virtual machine info for subscription {}({}) to S3".format(target_sub.display_name,target_sub.subscription_id))
        save_resource_to_s3("vm/instance", vmid, resource_item)

    else:
        logger.error("Unable to complete virtual machine processing {}({})".format(target_sub.display_name, target_sub.subscription_id))
        raise ClientError(f"Error getting virtual machine information for subscription {target_sub.display_name}({target_sub.subscription_id})")

