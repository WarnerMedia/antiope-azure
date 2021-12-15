class resourceEndpoints():
    def __init__(self, **kwargs):
        # set defaults
        self.opts = {}
        self.opts["azure_management_endpoint"] = "https://management.azure.com"
        self.opts["excludes"] = ['sqldb', 'vminstance'] # sqldb is broken and vminstance is handled by inventory_vm lambda

        for key in kwargs:
            self.opts[key] = kwargs[key]

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
                "path": '/providers/Microsoft.Sql/servers?api-version=2021-02-01-preview',
                "azcli": "az sql server list",
                "s3prefix": "sql/server",
                "a_res_type": "SQLServer"
                },
            "sqldb": {
                "comment": "requires sqlserver info like id, resourcegroup and server so must be a subsiquent call to 'sqlserver' call - seems broken in cli so won't work here",
                "path": 'resourceGroups/_resource_group_/providers/Microsoft.Sql/servers/_server_name_/databases?api-version=2021-02-01-preview',
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
                "a_res_type": "VM::VirtualMachine"
                },
            "networkinterface": {
                "comment": "produces a list of network configs with vm ids to be mapped back",
                "path": 'providers/Microsoft.Network/networkInterfaces?api-version=2021-03-01',
                "azcli": "az network nic list",
                "s3prefix": "network/nic",
                "a_res_type": "Network::Nic"
                },
            "publicipaddresses": {
                "comment": "produces a list of network configs with vm ids to be mapped back",
                "path": 'providers/Microsoft.Network/publicIPAddresses?api-version=2021-03-01',
                "azcli": "az network public-ip list",
                "s3prefix": "network/publicip",
                "a_res_type": "Network::PublicIp"
                },
            "vmscaleset": {
                "path": 'providers/Microsoft.Compute/virtualMachineScaleSets?api-version=2021-07-01',
                "azcli": "az vmss list",
                "s3prefix": "vm/scaleset",
                "a_res_type": "VM::VMSSInstance"
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
        return( f'{self.opts[ "azure_management_endpoint"]}/subscriptions/{subscription}/{self.res[resource]["path"]}' )

    def getKnownResources(self, **kwargs):
        if "excludes" in kwargs:
            excludes = kwargs["excludes"]
        else:
            excludes = self.opts["excludes"]
        return(set( self.res.keys() ) - set(excludes) )

    def getS3Prefix(self, resource):
        return( self.res[resource]["s3prefix"] )
