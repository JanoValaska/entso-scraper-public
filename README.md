# ENTSO-E Data Scraper

A serverless, config-driven data collection system that downloads electricity market data from the ENTSO-E Transparency Platform and stores it in AWS S3 as CSV files.

## Features

- ✅ **Config-driven**: Add new data sources via EventBridge rules (no code changes)
- ✅ **Flexible time parsing**: Structured datetime objects with relative offsets
- ✅ **Automated deployment**: CI/CD pipeline with GitHub Actions
- ✅ **Well-tested**: 66 unit tests with 94% code coverage
- ✅ **Infrastructure as Code**: Complete Terraform setup with VPC, NAT, and Lambda
- ✅ **Cost-optimized**: Uses fck-nat (t4g.nano) instead of NAT Gateway (~$35/month savings)

## Architecture

- **AWS Lambda** (Python 3.11): Dynamic method invocation on `entsoe-py` client
- **Lambda Layer**: Dependencies packaged separately for fast code updates
- **Amazon S3**:
  - State bucket: Terraform remote state with encryption
  - Data bucket: CSV files organized by method name and parameters
- **Amazon EventBridge**: Scheduled triggers (3 demo rules included)
- **AWS VPC** (2 AZs): Private subnets for Lambda, public subnets for NAT
- **fck-nat** (t4g.nano): Cost-effective NAT instance for internet egress
- **AWS SSM Parameter Store**: Secure storage for ENTSO-E API token
- **CloudWatch Logs**: Structured logging with 14-day retention

## Prerequisites

- **AWS Account** with appropriate permissions
- **ENTSO-E API Token** - [Get it here](https://transparencyplatform.zendesk.com/hc/en-us/articles/12845911031188-How-to-get-security-token)
- **Terraform CLI** (v1.0+) installed locally
- **AWS CLI** configured with credentials
- **Python 3.11+** (for local development and testing)
- **Docker** (optional, for local Lambda layer builds)

## Manual Setup Required (One-Time)

Before running Terraform, complete these manual steps:

### 1. Create IAM Policy for Terraform

Create a managed policy that will be used by both the IAM user and the OIDC role:

1. Go to AWS Console → IAM → Policies → Create Policy
2. Click JSON tab and paste contents of `docs/policies/terraform-deployer-policy.json`
3. Name: `TerraformDeployerPolicy`
4. Description: "Permissions for Terraform to deploy ENTSO-E scraper infrastructure"
5. Create policy

### 2. Create IAM User for Terraform (Local Development)

Create an IAM user for local Terraform deployments:

1. Go to AWS Console → IAM → Users → Create User
2. User name: `TerraformDeployer`
3. Attach the `TerraformDeployerPolicy` created in step 1
4. Under "Security credentials" → Create Access Key → Choose "Command Line Interface (CLI)"
5. Save the Access Key ID and Secret Access Key

### 3. Create IAM Role for GitHub Actions (CI/CD)

Create an IAM role for GitHub Actions to use OIDC authentication:

**Step 3a: Create OIDC Identity Provider (if not exists)**

1. Go to AWS Console → IAM → Identity providers → Add provider
2. Provider type: OpenID Connect
3. Provider URL: `https://token.actions.githubusercontent.com`
4. Audience: `sts.amazonaws.com`
5. Add provider

**Step 3b: Create IAM Role**

1. Go to IAM → Roles → Create Role
2. Trusted entity type: Web identity
3. Identity provider: `token.actions.githubusercontent.com`
4. Audience: `sts.amazonaws.com`
5. GitHub organization: `YOUR_GITHUB_USERNAME`
6. GitHub repository: `YOUR_REPO_NAME`
7. Role name: `GitHubActionsDeployerRole`
8. Attach the `TerraformDeployerPolicy` created in step 1

**Step 3c: Update Trust Policy**

After creating the role, edit the trust policy to match `docs/policies/trust-policy-template.json`:

```bash
# Update the trust policy with your account ID and repo details
# Replace YOUR_ACCOUNT_ID and YOUR_GITHUB_ORG/YOUR_REPO
```

The trust policy should restrict access to your specific GitHub repository.

**Step 3d: Configure GitHub Secret**

1. Go to your GitHub repository → Settings → Secrets and variables → Actions
2. Add new repository secret:
   - Name: `AWS_ROLE_TO_ASSUME`
   - Value: `arn:aws:iam::YOUR_ACCOUNT_ID:role/GitHubActionsDeployerRole`

### 4. Configure AWS Credentials (Local Development)

Configure your local AWS CLI with the TerraformDeployer credentials:

```bash
aws configure --profile terraform-deployer
# Enter:
# - AWS Access Key ID: [from step 2]
# - AWS Secret Access Key: [from step 2]
# - Default region: eu-central-1
# - Default output format: json

# Set as active profile
export AWS_PROFILE=terraform-deployer
```

### 5. Store ENTSO-E API Token in SSM

Create the SSM parameter with your ENTSO-E API token:

```bash
aws ssm put-parameter \
  --name "/entso-scraper/demo/entso-api-token" \
  --value "YOUR_ENTSO_API_TOKEN_HERE" \
  --type "SecureString" \
  --description "ENTSO-E Transparency Platform API Token" \
  --region eu-central-1
```

**How to get your ENTSO-E token:**
1. Register at [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/)
2. Follow instructions: [How to get security token](https://transparencyplatform.zendesk.com/hc/en-us/articles/12845911031188-How-to-get-security-token)

### 6. Initial Manual Deployment

Follow the steps from "Manual Deployment Instructions" for initial deployment


---
## Deployment Options

### Option 1: Automated Deployment (Recommended)

The project includes a GitHub Actions workflow that automatically:
1. Builds Lambda layers in Docker (Amazon Linux compatibility)
2. Packages Lambda code
3. Runs Terraform plan/apply

**Prerequisites:**
- Complete steps 1, 3, 5, and 6 from "Manual Setup Required" above
- Skip step 2 (IAM user) and step 4 (local credentials) from "Manual Setup Required" if only using CI/CD

**Setup:**
1. Fork this repository
2. Configure the OIDC role and GitHub secret (see step 3 from "Manual Setup Required") in your forked repository
3. Push to `main` branch to trigger deployment

See `.github/workflows/terraform.yml` for the complete workflow.

**Notes:**
- GitHub Action can fail on 'terraform fmt -check' step. Run `terraform fmt -recursive infra/terraform` locally to fix formatting issues.
- GitHub Action can fail on 'terraform validate' step. Run `terraform validate` in `infra/terraform/envs/{env}` locally to fix validity issues.
---


### Option 2: Manual Deployment

**Prerequisites:**
- Complete steps 1, 2, 4, and 5 from "Manual Setup Required" above
- Skip step 3 (OIDC) and step 6 (initial deployment) from "Manual Setup Required" if only using manual deployment

Follow the steps from "Manual Deployment Instructions" for local Terraform deployment.

## Manual Deployment Instructions

### 1. Bootstrap Terraform State
First, you need to create the S3 bucket that will hold the Terraform state.

```bash
cd infra/terraform/bootstrap
# Edit terraform.tfvars to set aws_region and state_bucket_name
terraform init
terraform apply
```

### 2. Deploy Main Infrastructure

After bootstrapping, deploy the main infrastructure (Lambda, VPC, S3 data bucket, EventBridge).

```bash
# Build Lambda layer
bash infra/terraform/modules/lambda/build_layer.sh

cd infra/terraform/envs/demo
# Edit terraform.tfvars to set aws_region, environment and data_bucket_name
# The backend is already configured to use S3 in backend.tf
terraform init
terraform apply
```

**Note:** The main infrastructure state is automatically stored in S3 from the start (no migration needed).

## Configuration

The system is **config-driven** through EventBridge rules. No code changes are needed to add new data sources.

### EventBridge Rules

Three demo rules are configured in `infra/terraform/modules/eventbridge/main.tf`:

1. **Day-Ahead Prices (CZ)** - Daily at 2:00 AM UTC
2. **Actual Load (DE)** - Every 6 hours
3. **Generation Forecast (AT)** - Daily at 6:00 AM UTC

### Adding New Data Sources

To add a new data source, create a new EventBridge rule in Terraform with the method name and parameters:

```hcl
resource "aws_cloudwatch_event_rule" "new_data_source" {
  name                = "entso-scraper-new-source-demo"
  schedule_expression = "cron(0 12 * * ? *)"
}

resource "aws_cloudwatch_event_target" "new_data_source" {
  rule      = aws_cloudwatch_event_rule.new_data_source.name
  target_id = "NewDataSource"
  arn       = var.lambda_function_arn

  input = jsonencode({
    method_name = "query_installed_generation_capacity"
    parameters = {
      country_code = "FR"
      start = {
        date = "current_date"
        time = "day_start"
      }
      end = {
        date = "current_date"
        time = "day_end"
      }
      timezone = "Europe/Paris"
    }
  })
}
```

## Testing

This project includes comprehensive unit tests (66 tests, 94% coverage) and manual integration test scenarios.

For detailed testing instructions, see [tests/TESTING.md](tests/TESTING.md).

## Development

### Project Structure

```
src/
├── lambda_function.py    # Lambda handler with dynamic method invocation
├── utils.py             # Helper functions (time parsing, S3 key generation, validation)
├── requirements.txt     # Lambda dependencies
└── requirements-dev.txt # Development dependencies (pytest, mypy, etc.)

tests/
├── unit/               # Unit tests (pytest)
│   ├── test_lambda_function.py
│   └── test_utils.py
├── events/             # Test event payloads
└── TESTING.md         # Testing documentation

infra/terraform/
├── bootstrap/          # S3 bucket for state storage
├── envs/demo/         # Demo environment
└── modules/           # Reusable Terraform modules
```

### Lambda Deployment

Dependencies are packaged into a **Lambda Layer** using GitHub Actions:
- Keeps function code small
- Allows fast code-only updates
- Built in Docker for Amazon Linux compatibility

See `.github/workflows/terraform.yml` for the CI/CD pipeline.

## Teardown instructions

To avoid ongoing charges, destroy the infrastructure in reverse order:

```bash
# 0. Create dummy layer file if it doesn't exist (workaround for Terraform destroy)
cd infra/terraform/modules/lambda
if [ ! -f deps-layer.zip ]; then
  echo "dummy" | zip deps-layer.zip -
fi

# 1. Empty the data bucket BEFORE destroying (Terraform won't delete non-empty buckets)
# NOTE: If the bucket has versioning enabled, then the simplest way to empty the bucket is via Amazon Console -> S3 -> select bucket -> Empty   
aws s3 rm s3://YOUR-DATA-BUCKET-NAME/ --recursive --region eu-central-1

# 2. Destroy main infrastructure
cd infra/terraform/envs/demo
terraform destroy

# 3. Empty the data bucket BEFORE destroying (Terraform won't delete non-empty buckets)
# NOTE: If the bucket has versioning enabled, then the simplest way to empty the bucket is via Amazon Console -> S3 -> select bucket -> Empty
aws s3 rm s3://YOUR-STATE-BUCKET-NAME/ --recursive --region eu-central-1

# 4. Destroy bootstrap (state bucket)
cd ../../../bootstrap
terraform destroy

```

**Notes:**
- Step 0 is needed because the Lambda layer expects the zip file to exist during destroy
- Step 1 must happen BEFORE `terraform destroy` to avoid BucketNotEmpty errors
- The state bucket will fail to destroy if not empty. Use the AWS CLI command above or empty it manually in AWS Console.
- If the bucket has versioning enabled, then the simplest way to empty the bucket is via Amazon Console -> S3 -> select bucket -> Empty
---

## Documentation

- **[PRD.md](docs/PRD.md)** - Product requirements and goals
- **[SPEC.md](docs/SPEC.md)** - Engineering specification
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design and decisions
- **[DECISIONS.md](docs/DECISIONS.md)** - Architecture decision records (32 decisions)
- **[TESTING.md](tests/TESTING.md)** - Unit and integration testing guide
- **[STATUS.md](docs/STATUS.md)** - Project status and progress tracking
