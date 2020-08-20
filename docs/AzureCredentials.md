# Managing Azure Credentials

Antiope Azure requires Service Principal credentials in order to access the azure tenant(s). Antiope will pull these from AWS Secrets Manager. This page documents how to create and update that secret.


## Creating an Antiope Service Principal

*TODO*

## Format of the Secret
Regardless the number of Tenants, Antiope will pull one json object from Secrets Manager. The structure of that file should look like:
```json
{
  "<tenant_name>": {
    "application_id": "REPLACEME",
    "key": "REPLACEME",
    "tenant_id": "THIS_IS_YOUR_AZURE_AD_TENANT_ID"
  },
  "<second_tenant_name>": {
    "application_id": "REPLACEME",
    "key": "REPLACEME",
    "tenant_id": "THIS_IS_YOUR_AZURE_AD_TENANT_ID"
  }
}
```

## Commands to fetch and update the secret.

**Note:** The cloudformation template creates a KMS-CMK and Secret with a dummy-value. After the inital deployment, you will need to add the actual secret values.

* **Retrieve the Secret**
```bash
aws secretsmanager get-secret-value --secret-id VALUE_OF_pAzureServiceSecretName_FROM_MANIFEST --query 'SecretString' --output text | jq . > azure_cred.json
```
Note: you can omit the jq step if you don't have it. All it provides is better formating of the data retrieved from secrets manager.


* **Update the Secret**
```bash
aws secretsmanager update-secret --secret-id VALUE_OF_pAzureServiceSecretName_FROM_MANIFEST --region ${AWS_DEFAULT_REGION} \
            --secret-string file://azure_cred.json
````


**Note: Never commit azure_cred.json to github!!!** That specific filename is part of the .gitignore for this repo