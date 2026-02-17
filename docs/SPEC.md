# Engineering Specification — ENTSO-E Data Collection System

**Status:** Final
**Version:** 1.1
**Last updated:** 2026-02-10
**References:** PRD.md, ARCHITECTURE.md, DECISIONS.md

---

## 1) Scope

This specification defines the implementation details for the ENTSO-E data collection Lambda function and its configuration mechanism. It translates PRD requirements into precise, build-ready behavior.

**PRD Requirements Covered:**
- FR1: Data ingestion from ENTSO-E (entsoe-py)
- FR2: Store outputs in S3 as CSV
- FR3: Generic/flexible processing
- FR4: Config-driven endpoint expansion via EventBridge
- FR5: Time parameter parsing
- FR6: Scheduling via EventBridge

---

## 2) Functional Requirements Implementation

### FR1 — Data ingestion from ENTSO-E (entsoe-py)

**Implementation:**
- Runtime: **Python 3.11+**
- Library: **entsoe-py** (EntsoePandasClient)
- **Deployment Strategy:** Python dependencies (pandas, entsoe-py, etc.) are packaged into a **Lambda Layer** to keep the function package small and allow for faster code updates.
- Event payload specifies `method_name` (e.g., "query_day_ahead_prices")
- Event payload specifies `parameters` (arbitrary dict matching method signature)
- Lambda uses `getattr(client, method_name)` to dynamically invoke the method

**Method Validation:**
- Only methods starting with `query_` prefix are allowed
- This prevents calling internal/dangerous methods
- Validation happens before method invocation

**Error Handling:**
- Catch exceptions from entsoe-py client
- Log to CloudWatch with full context
- Lambda fails with non-zero exit code on error

---

### FR2 — Store outputs in S3 as CSV

**S3 Key Structure:**
```
s3://bucket/{method_name}/{encoded_params}__created_{timestamp}.csv
```

**Example:**
```
s3://entso-data-bucket/query_day_ahead_prices/country_code_CZ__start_20260204T000000Z__end_20260205T000000Z__created_20260205T143022Z.csv
```

**Key Generation Rules:**
- Two-level hierarchy: `method_name/` then filename
- Filename encodes all parameters: `{key}_{value}__` format
- Parameters ordered by method signature order (if available), then alphabetically
- Special characters in values sanitized (`:` → `-`, `/` → `-`, spaces → `-`)
- Timestamp values formatted as: `YYYYMMDDTHHMMSSz` (ISO 8601 basic format, UTC)
- Execution timestamp added with `__created_` prefix: `YYYYMMDDTHHMMSSz` (UTC)
- Use `__` (double underscore) as separator between parameter groups
- Use `_` (single underscore) within key-value pairs
- Other special characters removed (except alphanumeric, `-`, `_`)

**CSV Format:**
- UTF-8 encoding
- Standard CSV format (comma-separated, quoted strings)
- Preserve DataFrame output from entsoe-py (no schema transformation)
- Include headers
- Index handling: `index=True` with `index_label="timestamp"` to preserve time-series data

---

### FR3 — Generic / flexible processing

**Implementation:**
- Dynamic method invocation via `getattr(client, method_name)`
- Parameter dict passed directly to method: `method(**parameters)`
- DataFrame output saved as-is with `df.to_csv()`
- No assumptions about parameter names or DataFrame schema
- Unknown/extra fields preserved in CSV

---

### FR4 — Config-driven endpoint expansion via EventBridge

**Event Payload Schema:**
```json
{
  "method_name": "query_day_ahead_prices",
  "parameters": {
    "country_code": "CZ",
    "start": {
      "date": "current_date",
      "time": "day_start",
      "offset": "-1d"
    },
    "end": {
      "date": "current_date",
      "time": "day_start"
    },
    "timezone": "Europe/Prague"
  }
}
```

**Requirements:**
- EventBridge rule payload contains all configuration
- Each rule can have its own schedule (cron expression)
- Lambda is method-agnostic
- No code changes needed to add new endpoints

---

### FR5 — Time Parameter Parsing

**Structured Datetime Objects:**
`start` and `end` parameters must be dict objects with the following schema:
- `date`: `"current_date"` or `"YYYY-MM-DD"`
- `time`: `"current_time"`, `"day_start"`, `"day_end"`, or `"HH:MM[:SS]"`
- `offset`: (Optional) `"+/-{number}{unit}"` where unit is `m` (minutes), `h` (hours), `d` (days), `w` (weeks), `M` (months).

**Timezone Handling:**
- Optional `timezone` parameter in `parameters` dict (defaults to `"UTC"`).
- Used only for interpreting relative tokens (`current_date`, `current_time`, `day_start`, etc.).
- `timezone` is NOT passed to the `entsoe-py` method.

**Parsing logic:**
1. Resolve `date` to a timezone-aware Timestamp at midnight.
2. Resolve `time` relative to the resolved `date`.
3. Apply `offset` (if present) to the combined timestamp.
4. Convert the final timestamp to UTC.
5. Validate that `end > start`.

---

### FR6 — Scheduling via EventBridge

**Initial Demo Rules:**

**Rule 1: Day-Ahead Prices (CZ)**
```json
{
  "method_name": "query_day_ahead_prices",
  "parameters": {
    "country_code": "CZ",
    "timezone": "Europe/Prague",
    "start": {"date": "current_date", "time": "day_start", "offset": "-1d"},
    "end": {"date": "current_date", "time": "day_start"}
  }
}
```
Schedule: `cron(0 2 * * ? *)` (Daily at 2:00 AM UTC)

**Rule 2: Actual Load (DE)**
```json
{
  "method_name": "query_load",
  "parameters": {
    "country_code": "DE",
    "timezone": "Europe/Berlin",
    "start": {"date": "current_date", "time": "current_time", "offset": "-24h"},
    "end": {"date": "current_date", "time": "current_time"}
  }
}
```
Schedule: `cron(0 */6 * * ? *)` (Every 6 hours)

**Rule 3: Generation Forecast (AT)**
```json
{
  "method_name": "query_generation_forecast",
  "parameters": {
    "country_code": "AT",
    "timezone": "Europe/Vienna",
    "start": {"date": "current_date", "time": "day_start"},
    "end": {"date": "current_date", "time": "day_start", "offset": "+7d"}
  }
}
```
Schedule: `cron(0 6 * * ? *)` (Daily at 6:00 AM UTC)

---

## 3) Data Contract

### CSV Output Format

**Approach:**
- Save DataFrame as-is using `df.to_csv()`
- No schema transformation
- Preserve index
- UTF-8 encoding
- Standard CSV format (comma-separated, quoted strings)

**Expected columns (example for day-ahead prices):**
```
DateTime,Price
2026-02-04 00:00:00+00:00,50.5
2026-02-04 01:00:00+00:00,52.3
```

**Note:** Schema varies by method - this is intentional for flexibility.

### S3 Storage Layout
```
s3://entso-data-bucket/
  query_day_ahead_prices/
    country_code_CZ__start_20260204T000000Z__end_20260205T000000Z__created_20260205T143022Z.csv
    country_code_DE__start_20260204T000000Z__end_20260205T000000Z__created_20260205T143030Z.csv
  query_load/
    country_code_DE__start_20260204T000000Z__end_20260205T000000Z__created_20260205T083015Z.csv
  query_generation_forecast/
    country_code_AT__start_20260205T000000Z__end_20260212T000000Z__created_20260205T060001Z.csv
```

---

## 4) Observability

### Logging

**CloudWatch Configuration:**
- Log group: `/aws/lambda/entso-scraper`
- Log retention: **14 days** (configurable in Terraform)
- Format: Structured JSON logging recommended

**Log Events:**
- Lambda invocation start (method, parameters)
- API token retrieved (no token value logged)
- Method execution start
- DataFrame shape/size
- S3 upload success (key, size)
- Errors with full context

**Example log entry:**
```json
{
  "timestamp": "2026-02-05T14:30:22Z",
  "level": "INFO",
  "event_type": "lambda_invocation",
  "method_name": "query_day_ahead_prices",
  "parameters": {"country_code": "CZ", "start": "-1d", "end": "today"},
  "parsed_parameters": {"country_code": "CZ", "start": "2026-02-04T00:00:00Z", "end": "2026-02-05T00:00:00Z"}
}
```

**Error log format:**
```json
{
  "level": "ERROR",
  "timestamp": "2026-02-05T14:30:22Z",
  "method_name": "query_day_ahead_prices",
  "parameters": {"country_code": "CZ", "start": "-1d", "end": "today"},
  "error": "NoMatchingDataError: No data found for specified period",
  "traceback": "..."
}
```

### Metrics & Alarms
**Initial version:** No custom metrics or alarms
**Future consideration:** Lambda error rate, invocation count, duration

---

## 5) Testing Strategy

### Unit Tests (pytest)

**Test Coverage:**
- Time parameter parsing (`parse_datetime_object()`)
  - Structured objects with `date`, `time`, `offset`.
  - Keywords: `current_date`, `current_time`, `day_start`, `day_end`.
  - Absolute dates: `2026-02-04`
  - Edge cases: invalid formats
- S3 key generation (`generate_s3_key()`)
  - Parameter encoding
  - Special character sanitization
  - Timestamp format
- Method name validation
  - Valid: `query_*` methods
  - Invalid: other method names

**Test file structure:**
```
tests/unit/
  test_lambda_function.py
  test_utils.py
```

### Manual Testing (documented in README)

**Test Scenarios:**
- Deploy infrastructure with Terraform
- Manually invoke Lambda with test event
- Verify CSV appears in S3 with correct naming
- Verify CSV content is valid
- Check CloudWatch logs for success/error
- Test error scenarios (invalid method, API errors)

---

## 6) CI/CD Pipeline (GitHub Actions)

**Workflow:** `.github/workflows/terraform.yml`

**Trigger:**
- `push` to `main`: Performs `terraform apply` to deploy changes.

**Pipeline Steps:**
1. **Checkout Code:** Retrieves repository content.
2. **Build Dependencies Layer:**
   - Executes `infra/terraform/modules/lambda/build_layer.sh`.
   - Uses a Docker-based build environment (SAM Python image) to ensure Amazon Linux compatibility.
   - Installs dependencies from `requirements-layer.txt`.
   - Packages result into `deps-layer.zip`.
3. **Setup Terraform:** Installs HashiCorp Terraform CLI.
4. **Configure AWS Credentials:**
   - Uses **OIDC (OpenID Connect)** for secure, secret-less authentication.
   - Assumes a designated IAM Role in the target account.
5. **Terraform Init:** Initializes remote backend and provider plugins.
6. **Terraform Plan:** Generates execution plan for review.
7. **Terraform Apply** (Main branch only): Automatically applies changes to infrastructure.

---

## 7) Implementation Notes

### Lambda Handler Pseudocode
```python
def handler(event, context):
    """
    Lambda handler for ENTSO-E data collection.
    """
    # 1. Validate event structure
    # 2. Validate method_name (starts with 'query_')
    # 3. Retrieve API token from SSM
    # 4. Parse time parameters (relative -> absolute)
    # 5. Initialize EntsoePandasClient(api_key=token)
    # 6. Dynamic method invocation: getattr(client, method_name)(**parameters)
    # 7. Convert DataFrame to CSV (BytesIO buffer)
    # 8. Generate S3 key from method_name + parameters + timestamp
    # 9. Upload to S3
    # 10. Log success
    # 11. Return success response
```

### Error Scenarios to Handle
- Invalid method name (doesn't start with `query_`)
- Method doesn't exist on EntsoePandasClient
- Invalid parameters for method (TypeError, missing required args)
- ENTSO-E API errors (rate limiting, invalid country code, no data)
- S3 upload failures
- SSM parameter not found

### Future Enhancements (Out of Scope)
- Store raw ENTSO-E XML alongside CSV outputs (`EntsoeRawClient`)
- Add remote Terraform state + locking (S3+DynamoDB *or* Terraform Cloud)
- Add CloudWatch alarms for Lambda errors/throttles/duration
- Add S3 lifecycle rules for retention, archival, and expiry
- Enable ad-hoc queries via Glue Data Catalog + Athena tables
- Add Grafana dashboards (typically backed by Athena queries)
- Automate API token rotation and safe rollout (Secrets Manager)
- Add DLQ / Lambda Destinations for failed async invocations
- Support multi-region deployment, scheduling, and data replication

---

## Appendix A — EventBridge Event Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["method_name", "parameters"],
  "properties": {
    "method_name": {
      "type": "string",
      "pattern": "^query_",
      "description": "Name of EntsoePandasClient method to invoke"
    },
    "parameters": {
      "type": "object",
      "description": "Parameters to pass to the method",
      "additionalProperties": true
    }
  }
}
```

**Example events:**
```json
{
  "method_name": "query_day_ahead_prices",
  "parameters": {
    "country_code": "CZ",
    "timezone": "Europe/Prague",
    "start": {"date": "current_date", "time": "day_start", "offset": "-1d"},
    "end": {"date": "current_date", "time": "day_start"}
  }
}
```

```json
{
  "method_name": "query_crossborder_flows",
  "parameters": {
    "country_code_from": "CZ",
    "country_code_to": "DE",
    "timezone": "UTC",
    "start": {"date": "2026-02-01", "time": "00:00:00"},
    "end": {"date": "2026-02-05", "time": "00:00:00"}
  }
}
```

```json
{
  "method_name": "query_generation",
  "parameters": {
    "country_code": "DE",
    "timezone": "Europe/Berlin",
    "start": {"date": "current_date", "time": "current_time", "offset": "-24h"},
    "end": {"date": "current_date", "time": "current_time"},
    "psr_type": "B01"
  }
}
```

---

**End of SPEC**
