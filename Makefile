# Earshot task runner (owner: M6). Run `make help` to list the commands.
#
# One-time setup (Linux/macOS, or WSL on Windows):
#   python3.12 -m venv .venv && source .venv/bin/activate && make install
#   npm install -g aws-cdk          # CDK CLI (needs Node 20+)
#   aws configure                   # region us-east-1

SHELL := /bin/bash
.DEFAULT_GOAL := help

STAGE ?=
ALERT_EMAIL ?=
PY ?= python
CDK ?= cdk

CDK_CONTEXT := -c stage=$(STAGE) $(if $(ALERT_EMAIL),-c alert_email=$(ALERT_EMAIL))
BASE_STACK := earshot-$(STAGE)-base
PIPELINE_STACK := earshot-$(STAGE)-pipeline
CHECK_STACK := earshot-$(STAGE)-servicecheck

# Lets scripts import shared.names and earshot_infra.config.
export PYTHONPATH := $(CURDIR)/services:$(CURDIR)/infra

.PHONY: help install lint test synth diff bootstrap deploy-base seed pipeline-up pipeline-down destroy-all \
	account-check service-check service-check-down check-stage

help: ## Show this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-19s %s\n", $$1, $$2}'

install: ## Install Python dependencies into the active venv
	$(PY) -m pip install -r requirements-dev.txt

lint: ## Check Python code for real errors (undefined names, syntax); CI runs this
	$(PY) -m ruff check --select F,E9 .

test: ## Run the unit tests
	$(PY) -m pytest

synth: check-stage ## Build both CloudFormation templates (changes nothing in AWS)
	cd infra && $(CDK) synth $(CDK_CONTEXT) --quiet

diff: check-stage ## Show what a deploy would change
	cd infra && $(CDK) diff $(CDK_CONTEXT)

bootstrap: check-stage ## One-time CDK setup of your AWS account
	cd infra && $(CDK) bootstrap $(CDK_CONTEXT)

deploy-base: check-stage ## Build web/ (if it exists) and deploy the persistent stack
	@if [ -f web/package.json ]; then (cd web && npm ci && npm run build); else echo "web/ isn't set up yet (M1); skipping the web build"; fi
	cd infra && $(CDK) deploy $(BASE_STACK) $(CDK_CONTEXT) --require-approval never

seed: check-stage ## Load the catalog snapshot into DynamoDB (script: M2-03)
	@if [ ! -f scripts/catalog/seed_catalog.py ]; then echo "scripts/catalog/seed_catalog.py doesn't exist yet (M2-03)"; exit 1; fi
	$(PY) scripts/catalog/seed_catalog.py --stage $(STAGE)

pipeline-up: check-stage ## Deploy the hourly-billed pipeline stack
	cd infra && $(CDK) deploy $(PIPELINE_STACK) $(CDK_CONTEXT) --require-approval never
	@echo ">>> The pipeline is UP and bills by the hour. When you're done: make pipeline-down STAGE=$(STAGE)"

pipeline-down: check-stage ## Destroy the pipeline stack (after every session)
	cd infra && $(CDK) destroy $(PIPELINE_STACK) $(CDK_CONTEXT) --force

destroy-all: check-stage ## Destroy both stacks (dev stages only, never prod)
	@if [ "$(STAGE)" = "prod" ]; then echo "Refusing to destroy prod."; exit 1; fi
	cd infra && $(CDK) destroy --all $(CDK_CONTEXT) --force

account-check: ## Show the Lambda and EC2 limits that can block Earshot (read-only)
	$(PY) scripts/account_check.py

service-check: check-stage ## M6-03: deploy 1 tiny resource per service, show limits, destroy (15-30 min)
	@echo ">>> Deploying $(CHECK_STACK). CloudFront is slow to create and delete, so this takes 15-30 minutes."
	@cd infra && $(CDK) deploy $(CHECK_STACK) $(CDK_CONTEXT) -c servicecheck=true --require-approval never; \
	deploy_status=$$?; \
	$(PY) $(CURDIR)/scripts/account_check.py; \
	echo ">>> Destroying $(CHECK_STACK) (parts of it bill by the hour)"; \
	$(CDK) destroy $(CHECK_STACK) $(CDK_CONTEXT) -c servicecheck=true --force; \
	if [ $$deploy_status -eq 0 ]; then echo ">>> SERVICE CHECK PASSED: the account allows every service."; \
	else echo ">>> SERVICE CHECK FAILED: the CloudFormation error above names the resource (= service) that was blocked."; fi; \
	exit $$deploy_status

service-check-down: check-stage ## Destroy a leftover service-check stack
	cd infra && $(CDK) destroy $(CHECK_STACK) $(CDK_CONTEXT) -c servicecheck=true --force

check-stage:
	@if [ -z "$(STAGE)" ]; then echo "Set STAGE to your stage name, e.g.: make $(firstword $(MAKECMDGOALS)) STAGE=priya"; exit 1; fi
