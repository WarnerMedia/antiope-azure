# Deploy Instructions for Azure

## Prerequsites

1. Deploy the main Antiope Framework
2. Clone this repo as antiope-azure inside the antiope directory
3. Create the Azure Service Principals as described in [AzureCredentials](AzureCredentials.md)

## Create the Lambda Layer

```bash
cd antiope-azure
make layer env=FNORD
```

## Configuration

Antiope uses a config.ENV file to specify a few environment variables for the Makefile, and a cft-deploy Manifest file as the parameters to CloudFormation.

1. Create the Manifest
(replace FNORD with your environment name. ie dev, qa, prod, etc)
```bash
make manifest env=FNORD manifest=antiope-azure-FNORD-Manifest.yaml
echo "AZURE_MANIFEST=manifest=antiope-azure-FNORD-Manifest.yaml" >> ../config-files/config.FNORD
```

Edit the Manifest file:
1. Set `pAzureLambdaLayerPackage:` to match the output from the `make layer` command above
2. Remove the line with `LocalTemplate:` towards the top
3. Remove the `pBucketName:`, `pTemplateURL:` Parameters. They will be supplied by the Makefile
4. Provide a name for the SecretsManager credential as `pAzureServiceSecretName`
5. Provide the main Antiope Stack Name as `pAntiopeMainStackName`
4. Add the following as part if the StackPolicy block to prevent Cloudformation from touching your subscription table:
```yaml
  - Resource:
    - LogicalResourceId/SubscriptionDBTable
    Effect: Deny
    Principal: "*"
    Action:
      - "Update:Delete"
      - "Update:Replace"
```

## Validate everything

```bash
make cfn-validate-manifest env=prod
```

Make sure all the values look right

## Deploy

```bash
make deploy env=prod
```

**Add the Azure service principal secrets to the Secrets Manager secret that was created by `make deploy`**


## Promotion from lower environment

As Antiope uses Serverless Transforms as part of the CloudFormation process, you can re-use the transformed templates to promote code from a lower environment to an upper or production environment.

1. Generate a new Manifest for the upper environment using the `make manifest` command
2. Make sure to copy the LambdaLayer package from the lower environment's bucket to the upper environment.
3. Get the value of `TemplateURL` from the stack outputs of the lower environment. This file points to the exact set of lambda and cloudformation used to deploy the lower environment.
3. Run the `make promote` command:
```bash
make promote env=UPPER template=TEMPLATE_URL_FROM_STEP_3
```

Note, if the lower environment is in a different account, the antiope bucket will need a cross-account bucket policy granting access to the upper environment's account_id. The prefix the upper account requires is `deploy-packages/*`