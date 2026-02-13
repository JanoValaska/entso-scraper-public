# System Architecture — ENTSO-E Data Collection System

**Status:** Final
**Version:** 1.0
**Last updated:** 2026-02-09
**References:** PRD.md, SPEC.md, DECISIONS.md

---

## 1) Overview

This document describes the system architecture for the ENTSO-E data collection system, including AWS infrastructure components, networking design, and data flow.

**Architecture Context:**
- Serverless AWS Lambda-based data collection
- Event-driven scheduling via EventBridge
- VPC networking with internet egress via fck-nat
- All infrastructure provisioned via Terraform

---

## 2) System Components

### Application Layer
- **Lambda Function:** Python 3.11 runtime, executes data collection logic
  - Memory: 512 MB
  - Timeout: 300 seconds (5 minutes)
  - Deployed in private VPC subnets
  - Configuration via EventBridge event payloads

### Data Layer
- **S3 Bucket (Data):** Stores CSV outputs
  - Encryption: AES-256
  - Public access: Blocked
  - Bucket name: `entso-scraper-data-{env}` (configurable)

- **S3 Bucket (Terraform State):** Stores Terraform state
  - Versioning: Enabled
  - Encryption: AES-256
  - Public access: Blocked
  - Bucket name: `entso-scraper-terraform-state` (configurable)

### Scheduling Layer
- **EventBridge Rules:** Trigger Lambda on schedules
  - 3 initial rules with different cron schedules
  - Each rule contains complete configuration (method + parameters)

### Secrets Management
- **SSM Parameter Store:** Stores ENTSO-E API token
  - Type: SecureString (KMS encrypted)
  - Parameter name: `/entso-scraper/{environment}/entso-api-token`
  - Manual creation (not Terraform-managed)

### Observability
- **CloudWatch Logs:** Lambda execution logs
  - Log group: `/aws/lambda/entso-scraper`
  - Retention: 14 days (configurable)

---

## 3) Networking Architecture

### VPC Design (2 Availability Zones)

**VPC Configuration:**
- CIDR: `10.0.0.0/16`
- Spans 2 Availability Zones for stability

**Subnet Layout:**

**Public Subnets (for fck-nat):**
- `10.0.1.0/24` (AZ1)
- `10.0.2.0/24` (AZ2)

**Private Subnets (for Lambda):**
- `10.0.11.0/24` (AZ1)
- `10.0.12.0/24` (AZ2)

**Internet Gateway:**
- 1 Internet Gateway (IGW) attached to VPC

**Route Tables:**
- **Public Route Table:** `0.0.0.0/0 → IGW`
  - Associated with public subnets
- **Private Route Table:** `0.0.0.0/0 → fck-nat ENI`
  - Associated with private subnets

---

## 4) Internet Egress via fck-nat

**fck-nat Configuration:**
- **Instance Type:** ARM-based t4g.nano
- **AMI:** Latest fck-nat AMI
- **Placement:** Public subnet in AZ1 (`10.0.1.0/24`)
- **High Availability:** Single instance (HA not required for demo)
- **ENI Configuration:** Source/destination check disabled
- **Reference:** https://github.com/AndrewGuenther/fck-nat

**Rationale:**
- Cost-effective alternative to managed NAT Gateway
- Sufficient for demo/assignment requirements
- Project preference specified in original requirements

**Traffic Flow:**
```
Lambda (private subnet) → fck-nat ENI → IGW → Internet (ENTSO-E API)
```

---

## 5) Security Architecture

### IAM Permissions

**Lambda Execution Role:**
- `ssm:GetParameter` for `/entso-scraper/{environment}/entso-api-token`
- `s3:PutObject` for data bucket
- VPC networking permissions (ENI management)
- CloudWatch Logs write permissions

**Principle:** Least privilege access

### Token Management

**Production Pattern:**
- Token stored in SSM Parameter Store (SecureString)
- Lambda reads at runtime with caching
- Environment variable: `ENVIRONMENT` (not the token itself)

**Local Development Pattern:**
- Fallback to `ENTSO_API_TOKEN` environment variable
- Enables easy local testing without AWS credentials

**Lambda Token Access Logic:**
```python
# Cache token for warm Lambda invocations
_cached_token = None

def get_api_token():
    global _cached_token

    # Local development: use env var
    if 'ENTSO_API_TOKEN' in os.environ:
        return os.environ['ENTSO_API_TOKEN']

    # Production: read from SSM (with caching)
    if _cached_token is not None:
        return _cached_token

    env = os.environ.get('ENVIRONMENT', 'demo')
    parameter_name = f'/entso-scraper/{env}/entso-api-token'

    ssm = boto3.client('ssm')
    response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
    _cached_token = response['Parameter']['Value']
    return _cached_token
```

### S3 Security
- Public access blocked
- Server-side encryption enabled (AES-256 or KMS)
- Bucket policy: Lambda role only

---

## 6) Terraform Infrastructure

### Required AWS Resources

Terraform provisions:
- **Lambda function** (Python 3.11 runtime, 512 MB memory, 300s timeout)
- **IAM role and policies** (least privilege)
- **S3 bucket for data** (encrypted, no public access)
- **S3 bucket for Terraform state**
- **EventBridge rules** (3 initial rules with schedules)
- **SSM Parameter** (manual creation - see deployment guide)
- **VPC, subnets, routing**
- **fck-nat instance**
- **Security groups** (Lambda, fck-nat)
- **CloudWatch log group** (Lambda logs)

### Configurable Variables

**Terraform Variables:**
- `region` - AWS region (default: `eu-central-1`)
- `environment` - Environment name (default: `demo`)
- `state_bucket_name` - Terraform state bucket (default: `entso-scraper-terraform-state`)
- `data_bucket_name` - Data output bucket (default: `entso-scraper-data`)

### Resource Tagging Standard

All AWS resources tagged with:
```hcl
tags = {
  Project     = "entso-scraper"
  Environment = var.environment  # "demo", "dev", "prod"
  ManagedBy   = "terraform"
}
```

**Purpose:**
- Cost tracking and allocation
- Resource organization and filtering
- Clear ownership and management method

---

## 7) Terraform State Management

**Backend Configuration:**
- Remote backend: S3
- State file versioning: Enabled
- Encryption: Enabled
- State locking: None (DynamoDB table not used)

**Backend Configuration:**
```hcl
terraform {
  backend "s3" {
    bucket  = "entso-scraper-terraform-state"
    key     = "entso-scraper/terraform.tfstate"
    region  = "eu-central-1"
    encrypt = true
  }
}
```

**Bootstrap Process:**
1. Create state bucket manually or via bootstrap Terraform module
2. Configure backend in main Terraform
3. Run `terraform init` to migrate state to S3

**Rationale:**
- Demonstrates production-ready thinking (remote state)
- Suitable for solo development/assignment context
- State versioning provides safety net
- Simpler than full locking setup

**Trade-offs:**
- ✅ Remote state enables collaboration and backup
- ✅ Versioning provides rollback capability
- ⚠️ No locking: Requires discipline to avoid concurrent applies (acceptable for single developer)
- 💡 Locking can be added later (DynamoDB or Terraform Cloud) if team grows

---

## 8) Data Flow

### End-to-End Flow

```
1. EventBridge Rule (scheduled)
   ↓ (triggers with event payload)
2. Lambda Function (private subnet)
   ↓ (retrieves token)
3. SSM Parameter Store
   ↓ (token)
4. Lambda → fck-nat → IGW → Internet
   ↓ (API request)
5. ENTSO-E Transparency Platform
   ↓ (data response)
6. Lambda (processes DataFrame)
   ↓ (uploads CSV)
7. S3 Bucket (stores CSV)
   ↓ (logs success)
8. CloudWatch Logs
```

### Event-Driven Configuration Flow

```
EventBridge Rule Configuration:
{
  "schedule": "cron(0 2 * * ? *)",
  "event_payload": {
    "method_name": "query_day_ahead_prices",
    "parameters": {
      "country_code": "CZ",
      "start": "-1d",
      "end": "today"
    }
  }
}
   ↓
Lambda dynamically invokes method
   ↓
No code changes needed for new endpoints
```

---

## 9) Deployment Architecture

### Repository Structure
```
entso-scraper/
  lambda_function.py         # Main handler
  utils.py                   # Parsing, validation, S3 key generation
  requirements.txt           # Python dependencies
  terraform/
    main.tf                  # Main Terraform configuration
    variables.tf             # Input variables
    outputs.tf               # Output values
    modules/
      vpc/                   # VPC module
      lambda/                # Lambda module
      s3/                    # S3 module
      eventbridge/           # EventBridge module
      fck-nat/               # fck-nat module
  tests/
    test_time_parsing.py
    test_s3_key_generation.py
    test_validation.py
  docs/
    INDEX.md
    PRD.md
    SPEC.md
    ARCHITECTURE.md
    DECISIONS.md
    source/
      BUSINESS_CASE_2025-02-06.md
```

### Deployment Steps
1. Create SSM parameter for API token (manual)
2. Configure Terraform variables
3. `terraform init`
4. `terraform plan`
5. `terraform apply`
6. Verify resources and test Lambda invocation

---

## 10) SSM Parameter Setup

**Parameter Details:**
- **Name:** `/entso-scraper/{environment}/entso-api-token`
- **Type:** `SecureString` (KMS encrypted)
- **Environment-specific:** Uses `{environment}` variable
- **Example for demo:** `/entso-scraper/demo/entso-api-token`

**Creation Command:**
```bash
aws ssm put-parameter \
  --name "/entso-scraper/demo/entso-api-token" \
  --value "YOUR_ENTSO_API_TOKEN_HERE" \
  --type "SecureString" \
  --description "ENTSO-E Transparency Platform API Token"
```

**Why Manual Creation:**
- ✅ Token never appears in Terraform state (security best practice)
- ✅ Can rotate token without redeploying Lambda
- ✅ Proper separation of secrets management

---

## 11) Cost Considerations

**Cost-Optimization Decisions:**
- **fck-nat** instead of managed NAT Gateway (significant savings)
- **Lambda memory:** 512 MB (balance of cost and performance)
- **Lambda timeout:** 5 minutes (sufficient for most queries)
- **CloudWatch log retention:** 14 days (configurable)
- **S3 Intelligent-Tiering:** Optional (can be added via lifecycle policies)

**Expected Monthly Costs (estimate for demo usage):**
- Lambda: < $1 (minimal invocations)
- fck-nat EC2: ~$3-5 (t4g.nano)
- S3 storage: < $1 (minimal data volume)
- EventBridge: Free tier
- CloudWatch Logs: Free tier
- **Total: ~$5-10/month**

---

**End of ARCHITECTURE**
