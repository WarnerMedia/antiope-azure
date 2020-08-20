
ifndef env
# $(error env is not set)
	env ?= dev
endif

include ../config-files/config.$(env)
export

# MAIN_STACK_NAME is custom to your deployment and should be the same for all Antiope Stacks
ifndef MAIN_STACK_NAME
        $(error MAIN_STACK_NAME is not set)
endif

ifndef BUCKET
        $(error BUCKET is not set)
endif

ifndef version
	export version := $(shell date +%Y%b%d-%H%M)
endif

# The full name of the stack in Cloudformation. This must match the manifest file
export AZURE_STACK_NAME=$(MAIN_STACK_NAME)-azure

# Filename for the CFT to deploy
export DEPLOY_PREFIX=deploy-packages
export AZURE_TEMPLATE=cloudformation/Azure-Inventory-Template.yaml
OUTPUT_TEMPLATE_PREFIX=azure-Template-Transformed
OUTPUT_TEMPLATE=$(OUTPUT_TEMPLATE_PREFIX)-$(version).yaml
TEMPLATE_URL ?= https://s3.amazonaws.com/$(BUCKET)/$(DEPLOY_PREFIX)/$(OUTPUT_TEMPLATE)
CONFIG_PREFIX=config-files

export LAMBDA_PACKAGE=$(AZURE_STACK_NAME)-lambda-$(version).zip
export LAYER_PACKAGE=$(AZURE_STACK_NAME)-lambda-layer-$(version).zip

FUNCTIONS = $(RESOURCE_PREFIX)-common \
		$(RESOURCE_PREFIX)-inventory-subs \
		$(RESOURCE_PREFIX)-inventory-vm \
		$(RESOURCE_PREFIX)-report-subs \
		$(RESOURCE_PREFIX)-sub_handler \
		$(RESOURCE_PREFIX)-subscription \
		$(RESOURCE_PREFIX)-trigger_sub_actions

.PHONY: $(FUNCTIONS)

#
# Layer Targets
#
layer:
	cd lambda-layer && $(MAKE) layer


#
# Deploy New Code Targets
#

# Deploy a fresh version of code
deploy: cft-validate package cft-deploy push-config

deps:
	cd lambda && $(MAKE) deps

package: deps
	@aws cloudformation package --template-file $(AZURE_TEMPLATE) --s3-bucket $(BUCKET) --s3-prefix $(DEPLOY_PREFIX)/transform --output-template-file cloudformation/$(OUTPUT_TEMPLATE)  --metadata build_ver=$(version)
	@aws s3 cp cloudformation/$(OUTPUT_TEMPLATE) s3://$(BUCKET)/$(DEPLOY_PREFIX)/
# 	rm cloudformation/$(OUTPUT_TEMPLATE)

cft-deploy: package
ifndef AZURE_MANIFEST
	$(error AZURE_MANIFEST is not set)
endif
	cft-deploy -m ../config-files/$(AZURE_MANIFEST) --template-url $(TEMPLATE_URL) pTemplateURL=$(TEMPLATE_URL) pBucketName=$(BUCKET) --force


post-deploy: expire-logs

#
# Promote Existing Code Targets
#

# promote an existing stack to a new environment
# Assumes cross-account access to the lower environment's DEPLOY_PREFIX
promote: cft-promote push-config

cft-promote:
ifndef AZURE_MANIFEST
	$(error AZURE_MANIFEST is not set)
endif
ifndef template
	$(error template is not set)
endif
	cft-deploy -m ../config-files/$(AZURE_MANIFEST) --template-url $(template) pTemplateURL=$(template) pBucketName=$(BUCKET) --force


#
# Testing & Cleanup Targets
#
# Validate all the CFTs. Inventory is so large it can only be validated from S3
cft-validate:
	cft-validate -t $(AZURE_TEMPLATE)

test: cfn-validate
	cd lambda && $(MAKE) test

cft-validate-manifest: cft-validate
	cft-validate-manifest --region $(AWS_DEFAULT_REGION) -m ../config-files/$(AZURE_MANIFEST) --template-url $(TEMPLATE_URL) pBucketName=$(BUCKET)

# Clean up dev artifacts
clean:
	cd lambda && $(MAKE) clean
	cd lambda-layer && $(MAKE) clean
	rm cloudformation/$(OUTPUT_TEMPLATE_PREFIX)*

pep8:
	cd lambda && $(MAKE) pep8


#
# Management Targets
#

# target to generate a manifest file. Only do this once
# we use a lowercase manifest to force the user to specify on the command line and not overwrite existing one
manifest:
ifndef manifest
	$(error manifest is not set)
endif
	cft-generate-manifest -t $(AZURE_TEMPLATE) -m ../config-files/$(manifest) --stack-name $(AZURE_STACK_NAME) --region $(AWS_DEFAULT_REGION)

push-config:
	@aws s3 cp ../config-files/$(AZURE_MANIFEST) s3://$(BUCKET)/${CONFIG_PREFIX}/$(AZURE_MANIFEST)



#
# Rapid Development Targets
#
zipfile:
	cd lambda && $(MAKE) zipfile

# # Update the Lambda Code without modifying the CF Stack
update: zipfile $(FUNCTIONS)
	for f in $(FUNCTIONS) ; do \
	  aws lambda update-function-code --function-name $$f --zip-file fileb://lambda/$(LAMBDA_PACKAGE) ; \
	done

# Update one specific function. Called as "make fupdate function=<fillinstackprefix>-aws-inventory-ecs-inventory"
fupdate: zipfile
	aws lambda update-function-code --function-name $(function) --zip-file fileb://lambda/$(LAMBDA_PACKAGE) ; \

purge-logs:
	for f in $(FUNCTIONS) ; do \
	  aws logs delete-log-group --log-group-name /aws/lambda/$$f ; \
	done

expire-logs:
	for f in $(FUNCTIONS) ; do \
	  aws logs put-retention-policy --log-group-name /aws/lambda/$$f --retention-in-days 5 ; \
	done

