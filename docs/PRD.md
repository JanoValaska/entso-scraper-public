# PRD — ENTSO-E Data Collection System on AWS

**Status:** Final
**Owner:** Jan Valaska
**Last updated:** 2026-02-10

---

## 1) Summary
Implement an AWS Lambda-based data collection system that downloads data from the ENTSO-E Transparency Platform using the entsoe-py REST API client for selected countries/control areas, transforms it into CSV, and stores it in S3. All infrastructure must be provisioned via Terraform, including VPC networking with internet egress via fck-nat. The system is designed to be **fully configurable** through EventBridge event payloads, allowing any entsoe-py query method to be called without code changes.

---

## 2) Background / Context
This PRD is derived from a home assignment. It is intended to:
- Demonstrate ability to design a small data ingestion pipeline
- Use Terraform to deploy AWS resources (Lambda, IAM, S3, networking)
- Produce maintainable, extensible code suitable for adding more endpoints via configuration
- Show understanding of AWS best practices for serverless architectures

---

## 3) Goals
1. **Collect ENTSO-E data** using the entsoe-py library (REST API wrapper).
2. **Store collected data** in **S3** as **CSV files**.
3. Implement **generic/flexible processing** that works with any EntsoePandasClient method.
4. Make the system **config-driven** via EventBridge event payloads (no code changes to add endpoints).
5. Provision all infrastructure via **Terraform** (including VPC across **2 AZs** and fck-nat egress).
6. Implement **CI/CD pipeline** via GitHub Actions for automated testing, layer building, and deployment.
7. Provide **clear documentation**: setup, deployment, operation, and extension.

### Non-goals
- Dashboards/visualizations or downstream analytics
- Real-time streaming ingestion
- Full data warehouse design
- Complex governance / multi-account org setup
- Automatic rotation of ENTSO-E API tokens

---

## 4) Personas & Use cases
### Primary user (developer)
- Configure new data collection jobs by adding EventBridge rules
- Deploy with Terraform
- Inspect output CSVs in S3
- Add additional endpoints/control areas without modifying Lambda code

### Reviewer (hiring team)
- Validate IaC correctness and AWS best practices
- Evaluate code quality, extensibility, and documentation

---

## 5) Functional Requirements

### FR1 — Data ingestion from ENTSO-E (entsoe-py)
**Description:** The system must download data from ENTSO-E Transparency Platform using the entsoe-py library's EntsoePandasClient.

**Acceptance criteria:**
- Lambda can dynamically call any EntsoePandasClient method specified in the event payload
- Method name validation: only methods starting with `query_` prefix are allowed
- Handles common transient failures with appropriate error logging
- Successfully fetches data for configured control areas

---

### FR2 — Store outputs in S3 as CSV
**Description:** Store scraped data in S3 as CSV files with a systematic naming convention.

**Acceptance criteria:**
- Each Lambda execution produces one CSV file in S3
- CSV has headers and is readable by standard tooling (pandas, Excel, etc.)
- S3 bucket has public access blocked and encryption enabled
- CSV structure preserves DataFrame output from entsoe-py (no schema transformation)

**S3 Key Structure:**
```
s3://bucket/{method_name}/{encoded_params}__created_{timestamp}.csv
```

**Example:**
```
s3://entso-data-bucket/query_day_ahead_prices/country_code_CZ__start_20260204T000000Z__end_20260205T000000Z__created_20260205T143022Z.csv
```

**Key Details:**
- Parameters encoded as `{key}_{value}__` format
- Parameters ordered by method signature, then alphabetically
- Special characters sanitized (`:` → `-`, `/` → `-`, spaces → `-`)
- Timestamp values in ISO 8601 basic format: `YYYYMMDDTHHMMSSz`
- Execution timestamp with `__created_` prefix

---

### FR3 — Generic / flexible processing
**Description:** Lambda processes any EntsoePandasClient method without hardcoded logic.

**Acceptance criteria:**
- Dynamic method invocation via `getattr(client, method_name)`
- Parameter dict passed directly to method: `method(**parameters)`
- DataFrame output saved as-is with `df.to_csv()`
- No assumptions about parameter names or DataFrame schema
- Unknown/extra fields preserved in CSV

---

### FR4 — Config-driven endpoint expansion via EventBridge
**Description:** New data sources are added by creating new EventBridge rules, not code changes.

**Acceptance criteria:**
- EventBridge rule payload contains all configuration:
  - `method_name`: Name of EntsoePandasClient method
  - `parameters`: Dict of method parameters
- Each rule can have its own schedule (cron expression)
- Lambda is method-agnostic

---

### FR5 — Time Parameter Parsing
**Description:** Support structured datetime objects for `start` and `end` parameters, allowing combinations of relative and absolute time specifications.

**Acceptance criteria:**
- `start` and `end` are provided as structured objects:
  ```json
  {
    "date": "current_date" | "YYYY-MM-DD",
    "time": "current_time" | "day_start" | "day_end" | "HH:MM[:SS]",
    "offset": "+/-{number}{unit}" (optional)
  }
  ```
- Support for `timezone` parameter to interpret tokens (defaults to UTC).
- Relative offsets support units: `m` (minutes), `h` (hours), `d` (days), `w` (weeks), `M` (months).
- All parsed timestamps are converted to UTC before method invocation.
- Validation ensures `end` is after `start`.

---

### FR6 — Scheduling via EventBridge
**Description:** Use EventBridge rules for scheduling Lambda invocations.

**Acceptance criteria:**
- Each EventBridge rule defines its own cron schedule
- Manual invocation path works (for debugging/backfills)
- Initial demo includes 3 EventBridge rules with different schedules

---

## 6) Non-Functional Requirements

### NFR1 — Reliability and error handling
**Decision:** Handle exceptions in Lambda, log to CloudWatch for later inspection
- Lambda catches exceptions from entsoe-py client
- Structured error logging with context (method, parameters, error message)
- Lambda fails with non-zero exit code on error (visible in CloudWatch metrics)
- No automatic retries (rely on EventBridge retry logic)
- No `Dead Letter Queue`(DLQ) for initial version

### NFR2 — Security
**Decision:** Use AWS Systems Manager (SSM) Parameter Store for API token
- ENTSO-E API token stored as SSM Parameter (SecureString with KMS encryption)
- Parameter name: `/entso-scraper/{environment}/entso-api-token`
- Lambda IAM role has permission to read this parameter only
- Token fetched at Lambda cold start, cached for warm invocations
- Token must not appear in logs
- Least-privilege IAM policies for all resources
- S3 bucket encryption enabled (AES-256 or KMS)
- S3 bucket public access blocked

### NFR3 — Maintainability
- Automated CI/CD pipeline for reliable deployments
- Use of Lambda Layers to separate dependencies from application logic
- Clear module structure and readable code
- Type hints for Python functions
- Docstrings for key functions
- Documented assumptions and decisions in code comments
- README with comprehensive setup/deploy/operate instructions

### NFR4 — Cost-awareness
- Use fck-nat instead of managed NAT Gateway (cost-effective)
- Lambda memory: 256-512 MB (tune based on actual usage)
- Lambda timeout: 5 minutes (sufficient for most queries)
- S3 Intelligent-Tiering or lifecycle policies (optional)
- CloudWatch log retention: 7-14 days (configurable)

---

## 7) Repository deliverables
Single GitHub repo containing:
- **Application code:**
  - `lambda_function.py` (main handler)
  - `utils.py` (parsing, validation, S3 key generation)
  - `requirements.txt` (entsoe-py, boto3, pandas)
- **Terraform configuration:**
  - `main.tf`, `variables.tf`, `outputs.tf`
  - Modules for VPC, Lambda, S3, EventBridge, fck-nat
- **CI/CD Configuration:**
  - `.github/workflows/terraform.yml` (GitHub Actions workflow)
  - `infra/terraform/modules/lambda/build_layer.sh` (Dependency packaging)
- **Tests:**
  - `tests/` directory with unit tests
  - `requirements-dev.txt` (pytest, etc.)
- **Documentation:**
  - `README.md` (see Section 8)
  - `docs/INDEX.md` (entry point)
  - `docs/PRD.md` (this document)
  - `docs/SPEC.md` (technical specification)
  - `docs/ARCHITECTURE.md` (system design)
  - `docs/DECISIONS.md` (decision log)
  - `docs/source/BUSINESS_CASE_2025-02-06.md` (original assignment)

---

## 8) README Requirements

Must include:

### Prerequisites
- GitHub account
- AWS account (with $0 budget alert recommended)
- ENTSO-E Transparency Platform account & API token
- Terraform CLI installed locally
- Python 3.11+ (for local testing)

### Setup Instructions
1. Clone repository
2. Configure AWS credentials
3. Store ENTSO-E token in SSM Parameter Store
4. Configure Terraform variables (region, bucket name, etc.)

### Deployment Steps
1. `terraform init`
2. `terraform plan`
3. `terraform apply`
4. Verify resources created

### Manual Testing
- How to invoke Lambda manually with test event
- How to verify CSV output in S3
- How to check CloudWatch logs

### Adding New Data Sources
- How to add a new EventBridge rule
- Event payload format
- Available entsoe-py methods reference

### Teardown
- `terraform destroy`
- Manual cleanup if needed (S3 objects, logs)

---

## Appendix A — Source Assignment Reference

**Source:** docs/source/BUSINESS_CASE_2025-02-06.md (verbatim copy)

**Key Requirements from Assignment:**
> ENTSOE Assignment with Terraform Deployment
> Prerequisites: GitHub, AWS, transparency.entsoe.eu token, Terraform
> Develop AWS Lambda that scrapes ENTSO-E for selected countries/control areas, deploy infra with Terraform
> Store data in S3 as CSV
> Generic processing tolerant to response changes, reusable by config
> Terraform provisions Lambda, IAM, S3, scheduling, NAT or fck-nat, etc.
> Documentation, code quality, deploy instructions
> Submit as GitHub repo + PR + README
> Tech notes: 2 AZ VPC; prefer REST via entsoe-py; NAT via fck-nat preferred

---

## References

For detailed technical implementation, see:
- **SPEC.md** — Engineering specification (HOW to build)
- **ARCHITECTURE.md** — System design and infrastructure
- **DECISIONS.md** — Design decision log with rationale

---

**End of PRD**
