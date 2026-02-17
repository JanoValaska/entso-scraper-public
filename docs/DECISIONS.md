# Decision Log — ENTSO-E Data Collection System

**Last updated:** 2026-02-09

---

## Purpose

This document records all key architectural and design decisions made during the development of the ENTSO-E data collection system. Each decision includes context, options considered, rationale, and consequences.

---

## [2026-02-09] D1: Language and Runtime

**Context:** Need to choose programming language and runtime for Lambda function

**Options:**
1. Python 3.11+ - entsoe-py library available, pandas for DataFrames
2. Node.js - Good Lambda support but limited ENTSO-E client libraries
3. Java - More verbose, longer cold starts

**Decision:** Python 3.11+

**Rationale:**
- entsoe-py library provides excellent REST API wrapper
- pandas is industry standard for DataFrame processing
- Widely used for data pipelines
- Good Lambda support with fast cold starts

**Consequences:**
- Need to package pandas (large dependency)
- Suitable for data processing workloads

---

## [2026-02-09] D2: Configuration Approach

**Context:** How to make the system flexible for adding new endpoints

**Options:**
1. Configuration files (JSON/YAML) - Need to manage and deploy config
2. Environment variables - Limited flexibility
3. EventBridge event payloads - Configuration in event itself

**Decision:** EventBridge event payloads

**Rationale:**
- Clean separation of concerns
- No config files to manage
- Each rule is self-contained
- Easy to add new rules without code changes

**Consequences:**
- Configuration lives in Terraform EventBridge rules
- Lambda must parse and validate event structure

---

## [2026-02-09] D3: Dynamic Method Invocation

**Context:** How to call arbitrary EntsoePandasClient methods

**Options:**
1. Hardcode methods - Not flexible
2. Method registry/mapping - Requires maintenance
3. Dynamic invocation via getattr() - Fully flexible

**Decision:** Dynamic via `method_name` + `parameters` in event

**Rationale:**
- Maximum flexibility
- Any EntsoePandasClient method callable without code changes
- Simple implementation

**Consequences:**
- Must validate method names for security
- Runtime errors possible if method doesn't exist

---

## [2026-02-09] D4: Method Validation Security

**Context:** Dynamic method invocation could call dangerous methods

**Options:**
1. No validation - Security risk
2. Whitelist specific methods - Requires maintenance
3. Prefix-based validation - Natural boundary

**Decision:** Only allow methods starting with `query_` prefix

**Rationale:**
- Natural security boundary (all data query methods use this prefix)
- Prevents calling internal/dangerous methods
- No maintenance overhead

**Consequences:**
- Cannot call non-query methods (acceptable limitation)
- Clear contract for allowed operations

---

## [2026-02-09] D5: Time Parsing Support

**Context:** Need flexible time specifications for scheduling

**Options:**
1. Only absolute dates - Less flexible
2. Relative time support - More user-friendly
3. Both - Best of both worlds

**Decision:** Support relative (`-1d`, `+7d`) and absolute dates

**Rationale:**
- Flexible scheduling (e.g., "always yesterday")
- Simple implementation with pandas
- Covers common use cases

**Consequences:**
- Need parsing logic in Lambda
- Must handle edge cases and errors

---

## [2026-02-09] D6: Time Unit Convention

**Context:** What units to support for relative time offsets

**Options:**
1. Word-based (days, hours) - More verbose
2. Single-letter (d, h, m) - More compact
3. Case-sensitive abbreviations - Balance

**Decision:** `m`=minutes, `h`=hours, `d`=days, `w`=weeks, `M`=months (case-sensitive)

**Rationale:**
- Unambiguous
- Supports common use cases
- Case sensitivity distinguishes minutes (m) from months (M)

**Consequences:**
- Users must follow exact case convention
- Documentation must be clear about case sensitivity

---

## [2026-02-09] D7: Time Keywords

**Context:** Which keyword shortcuts to support

**Options:**
1. Many keywords (yesterday, tomorrow, etc.) - More options
2. Few keywords (now, today) - Simpler
3. Only relative offsets - Most consistent

**Decision:** Only `now` and `today` (no `yesterday`/`tomorrow`)

**Rationale:**
- Consistency - use `+1d`/`-1d` instead for uniformity
- Simpler implementation
- Fewer special cases

**Consequences:**
- Users must use offsets for yesterday/tomorrow
- More consistent syntax overall

---

## [2026-02-09] D8: DataFrame to CSV Transformation

**Context:** How to convert DataFrame to CSV

**Options:**
1. Schema transformation - Normalize structure
2. Direct conversion - Preserve original
3. Custom formatting - More control

**Decision:** Direct `df.to_csv()`, no transformation

**Rationale:**
- Simplicity
- Preserves original structure
- Generic across all methods

**Consequences:**
- CSV schema varies by method
- Downstream consumers must handle variability

---

## [2026-02-09] D9: S3 Path Structure

**Context:** How to organize CSV files in S3

**Options:**
1. Flat structure - Simple but not scalable
2. Date partitioning - Good for time-series
3. Method-based hierarchy - Self-documenting

**Decision:** `{method_name}/{encoded_params}__{timestamp}.csv`

**Rationale:**
- Two-level hierarchy (method, then file)
- All params in filename (self-documenting)
- Truly generic (works for any method)

**Consequences:**
- Long filenames with many parameters
- Need sanitization for special characters

---

## [2026-02-09] D10: S3 Timestamp Meaning

**Context:** What timestamp to use in filename

**Options:**
1. Data date - When data is from
2. Execution time - When Lambda ran
3. Both - More complex

**Decision:** Execution/creation time (not data date)

**Rationale:**
- Always available
- Works for any method
- Useful for operational queries

**Consequences:**
- Data date must be inferred from parameters
- Clear for operational tracking

---

## [2026-02-09] D11: Error Handling Strategy

**Context:** How to handle errors in Lambda

**Options:**
1. Silent failures - Bad for observability
2. Retry logic - Complex
3. Fail fast with logging - Simple and clear

**Decision:** Catch exceptions, log to CloudWatch, Lambda fails

**Rationale:**
- Visibility via logs
- CloudWatch metrics show failures
- Simple approach

**Consequences:**
- No automatic retries (rely on EventBridge)
- Must monitor CloudWatch for errors

---

## [2026-02-09] D12: Multi-Country Handling

**Context:** How to handle multiple countries

**Options:**
1. Lambda loops over countries - More complex
2. EventBridge rules handle iteration - Cleaner
3. Fan-out pattern - Over-engineered

**Decision:** No special handling, pass params as-is to method

**Rationale:**
- Keeps Lambda generic
- EventBridge rules handle iteration if needed
- Simpler implementation

**Consequences:**
- Need separate EventBridge rule per country
- More rules but cleaner Lambda code

---

## [2026-02-09] D13: Token Storage

**Context:** Where to store ENTSO-E API token

**Options:**
1. Environment variable - Appears in console/Terraform state
2. Secrets Manager - More expensive
3. SSM Parameter Store - Good balance

**Decision:** SSM Parameter Store (SecureString)

**Rationale:**
- Standard AWS practice for simple secrets
- Cost-effective
- Proper security (KMS encrypted)

**Consequences:**
- Manual creation step
- Lambda needs SSM read permission

---

## [2026-02-09] D14: NAT Gateway Choice

**Context:** How to provide internet egress for Lambda

**Options:**
1. AWS Managed NAT Gateway - Expensive (~$30/month)
2. fck-nat - Cost-effective (~$3-5/month)
3. No VPC - Security concern

**Decision:** fck-nat

**Rationale:**
- Assignment preference
- Cost-effective
- Sufficient for demo

**Consequences:**
- Need to manage EC2 instance
- Single point of failure (acceptable for demo)

---

## [2026-02-09] D15: Initial EventBridge Rules

**Context:** Which endpoints to include in demo

**Options:**
1. Single endpoint - Too simple
2. Multiple endpoints - Shows diversity
3. All possible endpoints - Over-engineered

**Decision:** 3 rules (day-ahead prices CZ, load DE, generation forecast AT)

**Rationale:**
- Demonstrates diversity of methods
- Different countries
- Different schedules

**Consequences:**
- Good showcase of flexibility
- Sufficient for demo without overcomplicating

---

## [2026-02-09] D16: Testing Approach

**Context:** What level of testing to include

**Options:**
1. No tests - Not professional
2. Full integration tests with mocks - Over-engineered
3. Unit tests + manual testing - Balanced

**Decision:** Unit tests for logic + manual testing documented

**Rationale:**
- Shows best practices
- Not over-engineering
- Practical for assignment

**Consequences:**
- Need pytest setup
- Manual testing requires clear documentation

---

## [2026-02-09] D17: Terraform State Management

**Context:** Where to store Terraform state

**Options:**
1. Local state - Not production-ready
2. S3 with DynamoDB locking - Full production setup
3. S3 without locking - Good middle ground

**Decision:** S3 remote backend (without DynamoDB locking)

**Rationale:**
- Demonstrates production-ready mindset
- Suitable for solo development
- Versioning for safety
- Can add locking later

**Consequences:**
- Need to create state bucket
- Requires discipline for concurrent applies
- Shows understanding of production patterns

---

## [2026-02-09] D18: AWS Region

**Context:** Which AWS region to default to

**Options:**
1. us-east-1 - Most common
2. eu-central-1 - Closer to ENTSO-E
3. Fully configurable - Most flexible

**Decision:** Configurable variable, default `eu-central-1`

**Rationale:**
- Flexibility for deployment
- EU region for ENTSO-E data proximity
- Lower latency

**Consequences:**
- Must document region choice
- Resource availability may vary by region

---

## [2026-02-09] D19: Environment Naming

**Context:** How to name the default environment

**Options:**
1. "prod" - Misleading for demo
2. "dev" - Generic
3. "demo" - Honest naming

**Decision:** Variable-based, default `demo`

**Rationale:**
- Production-ready pattern
- Allows multi-environment deployment
- Honest naming for assignment

**Consequences:**
- Shows understanding of multi-env patterns
- Clear this is a demo deployment

---

## [2026-02-09] D20: Lambda Configuration

**Context:** What memory and timeout to use

**Options:**
1. 128 MB / 30s - Minimal
2. 512 MB / 300s - Balanced
3. 1024 MB / 900s - Over-provisioned

**Decision:** 512 MB memory, 300s timeout

**Rationale:**
- AWS recommended defaults for data processing
- Room for larger datasets
- Not over-provisioned

**Consequences:**
- Higher cost but more reliable
- Can tune down if needed

---

## [2026-02-09] D21: VPC CIDR Block

**Context:** What CIDR block to use for VPC

**Options:**
1. 10.0.0.0/24 - Too small
2. 10.0.0.0/16 - Standard choice
3. 172.16.0.0/16 - Alternative

**Decision:** `10.0.0.0/16` with `/24` subnets

**Rationale:**
- Standard private range
- Sufficient address space
- Industry convention

**Consequences:**
- 65,536 addresses available
- Room for growth

---

## [2026-02-09] D22: fck-nat Placement

**Context:** Where to place fck-nat instance

**Options:**
1. Both AZs - High availability
2. Single AZ - Cost-effective
3. Auto Scaling Group - Over-engineered

**Decision:** Single instance in AZ1 public subnet

**Rationale:**
- Cost-effective
- Sufficient for demo
- HA not required

**Consequences:**
- Single point of failure (acceptable for demo)
- Can add HA later if needed

---

## [2026-02-09] D23: S3 Bucket Naming

**Context:** How to name S3 buckets

**Options:**
1. Random suffixes - Unique but not readable
2. Account ID suffix - Readable and unique
3. Simple names - May conflict

**Decision:** `entso-scraper-terraform-state` and `entso-scraper-data-{env}`

**Rationale:**
- Clear purpose indication
- Can add account ID suffix if conflicts occur

**Consequences:**
- May need to adjust if names are taken
- Clear naming convention

---

## [2026-02-09] D24: Resource Tagging

**Context:** What tags to apply to AWS resources

**Options:**
1. No tags - Not production-ready
2. Minimal tags - Good enough
3. Extensive tags - Over-engineered

**Decision:** Standard minimal tags (Project, Environment, ManagedBy)

**Rationale:**
- Production-ready practice
- Cost tracking and organization
- Clear ownership

**Consequences:**
- All resources tagged consistently
- Easy to track costs by project/environment

---

## [2026-02-09] D25: SSM Parameter Naming

**Context:** How to structure SSM parameter names

**Options:**
1. Manual creation in Terraform - Token in state
2. Manual creation, environment-aware - Secure and flexible
3. No SSM, use environment vars - Less secure

**Decision:** Manual creation, name `/entso-scraper/{env}/entso-api-token`

**Rationale:**
- Security best practice (token not in state)
- Environment-aware for multi-env
- Production-ready pattern

**Consequences:**
- Manual step in deployment
- Better security
- Can rotate independently

---

## [2026-02-09] D26: Token Access Pattern

**Context:** How Lambda should retrieve token

**Options:**
1. Always from SSM - Production only
2. Always from environment - Development only
3. Hybrid approach - Best of both

**Decision:** Hybrid (SSM runtime read + local env var fallback)

**Rationale:**
- Production security with easy local development
- Caching for performance
- Flexible testing

**Consequences:**
- Need both code paths
- Clear documentation required

---

## [2026-02-09] D27: Lambda Environment Variables

**Context:** What environment variables to set on Lambda

**Options:**
1. Token in environment - Insecure
2. All config in environment - Mixed concerns
3. Only ENVIRONMENT variable - Minimal

**Decision:** `ENVIRONMENT` only (not token itself)

**Rationale:**
- Non-sensitive metadata
- Enables dynamic SSM parameter lookup
- Token never in Lambda config

**Consequences:**
- Must fetch token at runtime
- Better security posture

---

## [2026-02-09] D28: VPC Availability Zones

**Context:** How many AZs to span

**Options:**
1. Single AZ - Simplest
2. Two AZs - Balanced
3. Three AZs - Over-engineered

**Decision:** 2 AZs

**Rationale:**
- Balance of cost and reliability
- Demonstrates HA awareness
- Standard practice

**Consequences:**
- Higher cost than single AZ
- More resilient architecture
- Production-ready pattern

---

## [2026-02-09] D29: Data Source Library

**Context:** How to access ENTSO-E API

**Options:**
1. Direct REST calls - More control but more work
2. entsoe-py library - Well-maintained wrapper
3. SOAP client - Older protocol

**Decision:** entsoe-py REST client

**Rationale:**
- Well-maintained Python library
- Simplifies API integration
- Handles authentication and rate limiting

**Consequences:**
- Dependency on third-party library
- Abstraction over raw API
- Note: Assignment references UI URLs, but library uses REST endpoints

---

## [2026-02-09] D30: Dependency Management via Lambda Layers

**Context:** Lambda function has large dependencies (pandas, entsoe-py) which exceed the 50MB direct upload limit and slow down iterative code updates.

**Options:**
1. Bundle dependencies in the function package - Slow deployments, exceeds console editing limits.
2. Lambda Layers - Separates code from dependencies, faster deployments, reusable.
3. Container Image - Overkill for this use case.

**Decision:** Use Lambda Layers for Python dependencies.

**Rationale:**
- Keeps the main function code small and reviewable.
- Dependencies don't change as often as logic.
- Standard practice for pandas-based Lambda functions.

**Consequences:**
- Must manage layer build process (Docker-based to ensure compatibility).
- Function depends on layer ARN.

---

## [2026-02-09] D31: Automated Deployment via GitHub Actions

**Context:** Manual Terraform applies are error-prone and don't provide a clear audit trail for infrastructure changes.

**Options:**
1. Manual deployment - Risky, no history.
2. Local scripts - Better, but still manual.
3. GitHub Actions CI/CD - Automated, consistent, uses OIDC for security.

**Decision:** Implement GitHub Actions workflow for Terraform and Layer building.

**Rationale:**
- Automation ensures consistency between environments.
- OIDC (OpenID Connect) removes the need for long-lived AWS secrets in GitHub.

**Consequences:**
- Need to configure OIDC trust between GitHub and AWS.
- Build process requires Docker for Lambda Layer consistency.

---

## [2026-02-10] D32: Structured Time Parameters

**Context:** The previous simple relative/absolute time parsing (D5, D6, D7) was limited and didn't clearly handle timezones or combinations of absolute dates with relative offsets.

**Options:**
1. Keep the simple string parsing - Limited flexibility.
2. Use structured objects for `start`/`end` - More verbose but much more flexible and precise.

**Decision:** Use structured objects with `date`, `time`, and optional `offset` fields. Added a `timezone` parameter to the event.

**Rationale:**
- Explicit separation of date and time components.
- Clear timezone handling for relative tokens (e.g., `current_date` in `Europe/Bratislava`).
- Allows complex combinations like "current time with 2h lookback" or "day start with 1d offset".
- Consistent with industry patterns for complex scheduling/querying.

**Consequences:**
- EventBridge rules must be updated to the new format.
- Lambda logic updated to parse these structured objects.
- Enhanced validation (e.g., ensuring `end > start` after parsing).
- The `timezone` parameter is only used for parsing and is not passed to `entsoe-py`.

---

## [2026-02-17] D33: EventBridge Scheduler vs EventBridge Rules

**Context:** The initial implementation used EventBridge Rules for scheduling Lambda invocations. However, EventBridge Scheduler is the newer, more feature-rich service specifically designed for scheduling tasks.

**Options:**
1. Keep EventBridge Rules - Legacy approach, limited flexibility.
2. EventBridge Scheduler - Modern scheduling service with better features (one-time schedules, flexible schedules, retry policies).
3. Hybrid approach - Mix of both depending on use case.

**Decision:** Migrate to EventBridge Scheduler.

**Rationale:**
- EventBridge Scheduler is purpose-built for scheduling tasks.
- More flexible scheduling options (one-time, rate-based, cron expressions).
- Better visibility and management in AWS Console.
- Integrated retry and dead-letter queue support.
- EventBridge Rules are better suited for event-driven patterns, not periodic scheduling.
- AWS recommends Scheduler for time-based invocations.

**Consequences:**
- Terraform modules must be updated to use `aws_scheduler_schedule` instead of `aws_cloudwatch_event_rule`.
- IAM roles for Scheduler need to be created (separate from EventBridge Rules).
- Different API for managing schedules.
- Better operational visibility and control over scheduled tasks.
