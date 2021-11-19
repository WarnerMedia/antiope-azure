#!/usr/bin/env python3
"""
cloudguard.py - an attempt to normalize and simplify interactions with CloudGuard's REST api.
use: cg = CloudGuard( creds={ "key": "xxx", "secret": "xxx"} )
r = cg.getAzureSubs()
"""

import requests
import json 

class CloudGuard(dict):
    def __init__( self, opts=None, **kwargs ):
        # set defaults.
        self.opts = {}
        self.opts["endpoint"] = "https://api.dome9.com"
        if opts is not None:
            for key in opts:
                if key == "creds":
                    self.opts[ "auth" ] = (opts.creds["key"], opts.creds["secret"])
                else:
                    self.opts[key]=opts[key]
        for key in kwargs:
            if key == "creds":
                self.opts[ "auth" ] = (kwargs["creds"]["key"], kwargs["creds"]["secret"])
            else:
                self.opts[key]=kwargs[key]
        self.error = False
        self.getAzureSubs()
        if self.error is False:
            self.getOrgUnits()
            
    def r_getAzureSubs(self, **kwargs):
        call={}
        call.update( self.opts )
        call[ "headers" ] = {'Accept': 'application/json'}
        for key in kwargs:
            call[key]=kwargs[key]
        r = requests.get(f'{call["endpoint"]}/v2/AzureCloudAccount', params={}, headers=call["headers"], auth=call["auth"])
        return( r ) 

    def r_searchFindings(self, **kwargs):
        call={}
        call.update( self.opts )
        call[ "headers" ] = { 'Content-Type': 'application/json', 'Accept': 'application/json' }
        call[ "params" ] = {}
        for key in kwargs:
            call[key]=kwargs[key]
        r = requests.post(f'{call["endpoint"]}/v2/Compliance/Finding/search', params=call["params"], data=json.dumps( call["data"], default=str ), headers=call["headers"], auth=call["auth"] )
        return( r ) 

    def r_getOrgUnits(self, **kwargs):
        call={}
        call.update( self.opts )
        call[ "headers" ] = {'Accept': 'application/json'}
        for key in kwargs:
            call[key]=kwargs[key]
        r = requests.get(f'{call["endpoint"]}/v2/organizationalunit/view', params={}, headers=call["headers"], auth=call["auth"])
        return( r ) 

    def r_getCloudSecurityGroups(self, **kwargs):
        call={}
        call.update( self.opts )
        call[ "headers" ] = {'Accept': 'application/json'}
        for key in kwargs:
            call[key]=kwargs[key]
        r = requests.get(f'{call["endpoint"]}/v2/CloudSecurityGroup', params={}, headers=call["headers"], auth=call["auth"])
        return( r ) 

    def r_getAzureSecurityGroups(self, **kwargs):
        call={}
        call.update( self.opts )
        call[ "headers" ] = {'Accept': 'application/json'}
        for key in kwargs:
            call[key]=kwargs[key]
        r = requests.get(f'{call["endpoint"]}/v2/AzureSecurityGroup', params={}, headers=call["headers"], auth=call["auth"])
        return( r ) 

    def r_addAzureSub(self, subinfo, **kwargs):
        call={}
        call.update( self.opts )
        call[ "headers" ] = { 'Content-Type': 'application/json','Accept': 'application/json'}
        for key in kwargs:
            call[key]=kwargs[key]
        subscription={ "name": "Azure-account",
                        "subscriptionId": "*******",
                        "tenantId": "string",
                        "credentials": {
                            "clientId": "******",
                            "clientPassword": "******"
                        },
                        "operationMode": "Read",
                        "error": "string"
                        }
        subscription.update( subinfo )
        r = requests.post(f'{call["endpoint"]}/v2/AzureCloudAccount', params={}, data=json.dumps( subscription, default=str ), headers=call["headers"], auth=call["auth"] )
        return( r ) 

    def r_delAzureSub( self, cg_sub_id, **kwargs ):
        call={}
        call.update( self.opts )
        call[ "headers" ] = {'Accept': 'application/json'}
        for key in kwargs:
            call[key]=kwargs[key]
        r = requests.delete(f'{call["endpoint"]}/v2/AzureCloudAccount/{cg_sub_id}/DeleteForce', params={}, headers = call["headers"], auth=call["auth"])
        return( r ) 

    def getAzureSubs(self):
        self.error = False
        r = self.r_getAzureSubs()
        if r.status_code == 200:
            self.AzureSubscriptions = r.json()
            self.AzureSubsHash = { sub["subscriptionId"]:sub for sub in r.json() } 
        else:
            self.error = { "status_code": r.status_code, "call": "getAzureSubs", "message": r.content.decode("UTF-8") }

    def getOrgUnits(self):
        self.error = False
        r = self.r_getOrgUnits()
        if r.status_code == 200:
            self.OrgUnitsHash = { ou["name"]:ou for ou in r.json()["children"] }
        else:
            self.error = { "status_code": r.status_code, "call": "getOrgUnits",  "message": r.content.decode("UTF-8") }
    
    def addAzureSub( self, subinfo ):
        self.error = False 
        r = self.r_addAzureSub( subinfo )
        if r.status_code != 201:
            self.error = { "status_code": r.status_code, "call": "addAzureSub",  "message": r.content.decode("UTF-8") }

    def searchFindings( self, search_parms ):
        self.error = False 
        r = self.r_searchFindings( data=search_parms )
        if r.status_code != 201:
            self.error = { "status_code": r.status_code, "call": "searchFindings",  "message": r.content.decode("UTF-8") }
            return([])
        return( r.json() )

    def delAzureSub(self, azure_subscription_id ):
        self.error = False
        if azure_subscription_id in self.AzureSubsHash.keys():
            r = self.r_delAzureSub( self.AzureSubsHash[ azure_subscription_id ]["id"] )
            if r.status_code != 204:
                self.error = { "status_code": r.status_code, "call": "delAzureSub",  "message": r.content.decode("UTF-8") }
        else:
            self.error = { "status_code": 200, "call": "delAzureSub",  "message": f'{azure_subscription_id} does not exist.' }

    def getOUObj(self, ou_name):
        for name in self.OrgUnitsHash.keys():
            if self.OrgUnitsHash[ name ]["name"].upper() == ou_name.upper():
                return( self.OrgUnitsHash[ name ] )
        self.error = { "status_code": 200, "call": "getOUObj",  "message": f'{ou_name} does not exist.' }
        
if __name__ == '__main__':
    import logging 
    logging.basicConfig(level=logging.DEBUG)
    cg=CloudGuard( creds={ "key": "085879b4-b057-4a3b-a139-94f6709833e8", "secret": "44eydrhfu1hpynao7zh3bhts" } )
    # if cg.error is False:
    #     print( f'Found {len( cg.AzureSubsHash.keys())} azure subscriptions.' )
    #     print( f'Found {len( cg.OrgUnitsHash.keys())} org units.' )
    # else:
    #     print( f'{cg.error}')

    # # lets delete a subscription using the Azure Subscription Id.
    # # cg.delAzureSub( "dca16e9e-b9a9-4dab-826f-f9a12989b3ea" )
    # # if cg.error is not False:
    # #     print( f'{cg.error}')


    
    # subinfo={ "name": "azure-best-meta-build-release-sbx", 
    #           "subscriptionId": "dca16e9e-b9a9-4dab-826f-f9a12989b3ea", 
    #           "tenantId": "0eb48825-e871-4459-bc72-d0ecd68f1f39", 
    #           "credentials": { "clientId": "xxx", "clientPassword": "xxx" }}

    
    # ou_info = cg.getOUObj("turner") 
    # if cg.error is False:
    #     subinfo.update( { "organizationalUnitId": ou_info["id"],
    #             "organizationalUnitPath": ou_info["path"],
    #             "organizationalUnitName": ou_info["name"] })
    # else: 
    #     print( f'{cg.error}')
    #     exit( 0 )

    # print(f'===== Adding subscriptionfor {subinfo["name"]}')
    # cg.addAzureSub( subinfo )
    # if cg.error is not False:
    #     print( f'{cg.error}')

    # print("=====Azure Subscriptions after add")
    # cg.getAzureSubs()
    # if cg.error is not False:
    #     print( f'{cg.error}')
    # else:
    #     for sub in cg.AzureSubscriptions:
    #         print( f'{sub}')
        
    r = cg.r_getAzureSecurityGroups()
    if cg.error is not False:
        print( f'{cg.error}')
    else:
        print( "----")
        j = json.loads( r.content.decode("UTF-8"))
        print( json.dumps( j, indent=2, default=str ) )

    exit(0)

    search_params = {  
                    "pageSize":1000,
                    "filter": {},
                    "searchAfter":[ ]
                    }
    try:
        search_response = cg.searchFindings( search_params  )
        if cg.error is not False:
            print( f'{cg.error}')
        else:
            ncrs=[]
            while search_response["searchAfter"]:
                for finding in search_response["findings"]:
                    print( f'{finding["entityName"]} {finding["status"]}' )
                    if finding["entityName"] == "wmcso-dch-testnsg":
                        print( json.dumps( finding, indent=2 ))
                    ncrs.append( {
                        "warm": f'azure{finding["entityExternalId"].lower().replace("/",":")}',
                        "wmcvid": "",
                        "subscription_id": finding[ "cloudAccountExternalId" ],
                        "subscription_name": cg.AzureSubsHash[finding[ "cloudAccountExternalId" ]]["name"],
                        "region": finding["region"].replace(" ", "").lower(),
                        "resource": finding["entityName"],
                        "finding": finding["tag"],
                        "rule": finding["ruleName"],
                        "message": finding["ruleLogic"]
                        } )
                search_params.update({ "searchAfter": search_response["searchAfter"] })
                search_response = cg.searchFindings( search_params  )
                if cg.error is not False:
                    print( f'{cg.error}')  
                    break 
    except Exception as e:
        print( "something went wrong")
    # for ncr in ncrs:
    #     print( json.dumps( ncr, indent=2, default=str) )

            
            

# sample_finding = {
#                 "id": "fa2f96de-ed98-4852-8726-0a42a3f92f4f",
#                 "findingKey": "HYVZeilGeKsFyE2Jnz5M0A",
#                 "createdTime": "2021-10-26T17:10:20.699Z",
#                 "updatedTime": "2021-10-26T17:10:26.9811842Z",
#                 "cloudAccountType": "Azure",
#                 "comments": [],
#                 "cloudAccountId": "60919dc9-d36d-4318-8d97-6f4a492fd189",
#                 "cloudAccountExternalId": "8f552864-5a10-4399-9525-f6fc7f7bf16c",
#                 "organizationalUnitId": "e8f1225b-0a82-47ef-a6b6-b30689ace639",
#                 "organizationalUnitPath": "Warnerbros",
#                 "bundleId": 502002,
#                 "alertType": "Task",
#                 "ruleId": "",
#                 "ruleName": "Ensure Storage Account Blobs and Containers are not Publicly Accessible",
#                 "ruleLogic": "StorageAccount should have allowBlobPublicAccess=false",
#                 "entityDome9Id": "7|60919dc9-d36d-4318-8d97-6f4a492fd189|resourcegroup|cso-astra-lumberjack-rg|storageaccount|logs8c5cprodkrs",
#                 "entityExternalId": "/subscriptions/8f552864-5a10-4399-9525-f6fc7f7bf16c/resourceGroups/cso-astra-lumberjack-rg/providers/Microsoft.Storage/storageAccounts/logs8c5cprodkrs",
#                 "entityType": "StorageAccount",
#                 "entityName": "logs8c5cprodkrs",
#                 "entityNetwork": null,
#                 "entityTags": [
#                     {
#                     "key": "Purpose",
#                     "value": "ATT CSO ASTRA export log storage"
#                     }
#                 ],
#                 "severity": "High",
#                 "description": "When the AllowBlobPublicAccess property is set to disabled for a storage account it prevents the ability to create publicly accessible blobs and containers. Disallowing public access helps to prevent data breaches caused by undesired anonymous access.",
#                 "remediation": "*AUTO* astra\n\nTo disallow public access for a storage account in the Azure portal, follow these steps:\n\n1. Navigate to your storage account in the Azure portal.\n2. Locate the Configuration setting under Settings.\n3. Set Blob public access to Disabled.\n\nReferences:\nhttps://astra.att.com/knowledgecenter/pages/1376955482\nhttps://docs.microsoft.com/en-us/azure/storage/blobs/anonymous-read-access-configure",
#                 "tag": "astra-az-d9-sto-002",
#                 "region": "Korea South",
#                 "bundleName": "AT&T Azure Astra Custom Ruleset",
#                 "acknowledged": false,
#                 "origin": "ComplianceEngine",
#                 "lastSeenTime": "2021-10-26T17:10:20.699Z",
#                 "ownerUserName": null,
#                 "magellan": null,
#                 "isExcluded": false,
#                 "webhookResponses": null,
#                 "remediationActions": [],
#                 "additionalFields": [],
#                 "occurrences": [],
#                 "scanId": null,
#                 "status": "Active",
#                 "category": "",
#                 "action": "Detect",
#                 "labels": null
#                 }