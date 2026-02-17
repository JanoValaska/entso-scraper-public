# Testing Guide

This document provides instructions for testing the ENTSO-E Data Scraper Lambda function, including unit tests and manual integration tests.

---

## Unit Testing

### Prerequisites

- Python 3.11+ installed
- Virtual environment support

**On Debian/Ubuntu systems, install venv support:**
```bash
# Update package lists
sudo apt update

# Install venv module
sudo apt install python3-venv
# Or for specific version: sudo apt install python3.12-venv
```

### Setup

1. **Create a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate  # On Windows
```

2. **Install dependencies:**
```bash
pip install -r src/requirements.txt
pip install -r src/requirements-dev.txt
```

### Running Unit Tests

**Run all unit tests:**
```bash
pytest tests/unit/ -v
```

**Run with coverage report:**
```bash
pytest tests/unit/ -v --cov=src --cov-report=term-missing
```

**Run specific test file:**
```bash
pytest tests/unit/test_utils.py -v
pytest tests/unit/test_lambda_function.py -v
```

**Run specific test class:**
```bash
pytest tests/unit/test_utils.py::TestParseDatetimeObject -v
```

**Run specific test:**
```bash
pytest tests/unit/test_utils.py::TestParseDatetimeObject::test_parse_current_date_day_start -v
```

### Test Coverage

The unit test suite includes:

**test_utils.py (50 tests):**
- `get_api_token()` - Environment variable and SSM retrieval with mocking
- `parse_datetime_object()` - All keywords (current_date, current_time, day_start, day_end)
- `parse_datetime_object()` - All offset types (-1d, +7d, -6h, +30m, +1w, +1M)
- `parse_datetime_object()` - Timezone handling (UTC, Europe/Prague, etc.)
- `parse_event_parameters()` - Parameter parsing and validation
- `generate_s3_key()` - S3 key generation with various parameters
- `sanitize_parameter_value()` - Special character handling
- `validate_event()` - Event structure validation
- `validate_method_name()` - Method name prefix validation
- `format_datetime_utc_for_key()` - UTC timestamp formatting

**test_lambda_function.py (16 tests):**
- `handler()` - Successful Lambda invocation
- `handler()` - Validation errors (missing fields, invalid method prefix)
- `handler()` - Method not found errors
- `handler()` - S3 upload failures
- `handler()` - Missing environment variables
- `to_timeseries_dataframe()` - Series/DataFrame normalization
- `to_timeseries_dataframe()` - Timezone handling and sorting

### Expected Results

All tests should pass:
```
tests/unit/test_utils.py::TestGetApiToken::test_get_token_from_environment PASSED
tests/unit/test_utils.py::TestGetApiToken::test_get_token_from_ssm PASSED
...
tests/unit/test_lambda_function.py::TestHandler::test_handler_success PASSED
...

======================== XX passed in X.XXs ========================
```

---

## Manual Integration Testing

### Prerequisites

- AWS CLI configured with appropriate credentials
- Deployed infrastructure in `demo` environment
- ENTSO-E API token stored in SSM Parameter Store (`/entso-scraper/demo/entso-api-token`)

## Test Event Files

Test event JSON files are located in `tests/events/`:

- `test-day-ahead-prices.json` - Day-ahead electricity prices for Czech Republic (yesterday to today)
- `test-load.json` - Actual load data for Germany (last 6 hours)
- `test-generation-forecast.json` - Generation forecast for Austria (next 7 days)
- `test-invalid-method.json` - Invalid method name (for error handling test, missing 'start' parameter)

---

## Test 1: Manual Lambda Invocation

Test the Lambda function with a valid query for day-ahead prices.

```bash
aws lambda invoke \
  --function-name entso-scraper-lambda-demo \
  --cli-binary-format raw-in-base64-out \
  --payload file://tests/events/test-day-ahead-prices.json \
  --region eu-central-1 \
  response.json

cat response.json
```

**Expected Result:**
- HTTP 200 response
- Response body contains success message with S3 key
- No errors in response

**Verify CloudWatch Logs:**
```bash
aws logs tail /aws/lambda/entso-scraper-lambda-demo \
  --region eu-central-1 \
  --since 5m
```

**Verify S3 File Created:**
```bash
aws s3 ls s3://entso-scraper-data-demo/ --recursive --region eu-central-1
```

Expected file pattern: `query_day_ahead_prices/country_code_CZ__start_<timestamp>__end_<timestamp>__created_<timestamp>.csv`

**Download and verify CSV content:**
```bash
aws s3 cp s3://entso-scraper-data-demo/[S3_KEY] - --region eu-central-1 | head
```

Should contain CSV data with timestamps and price values.

---

## Test 2: Error Handling

Test Lambda function with invalid method name.

```bash
aws lambda invoke \
  --function-name entso-scraper-lambda-demo \
  --cli-binary-format raw-in-base64-out \
  --payload file://tests/events/test-invalid-method.json \
  --region eu-central-1 \
  response-error.json

cat response-error.json
```

**Expected Result:**
- HTTP 400 response
- Error message: "Parameters must contain both 'start' and 'end' as structured datetime objects"
- No CSV file created in S3

**Verify Error Logs:**
```bash
aws logs tail /aws/lambda/entso-scraper-lambda-demo \
  --region eu-central-1 \
  --since 5m \
  --filter-pattern "ERROR"
```

---

## Test 3: Time Parameter Parsing

Test structured datetime objects with relative time offsets and keywords.

**Test with relative time offset (+7d):**
```bash
aws lambda invoke \
  --function-name entso-scraper-lambda-demo \
  --cli-binary-format raw-in-base64-out \
  --payload file://tests/events/test-generation-forecast.json \
  --region eu-central-1 \
  response-relative.json

cat response-relative.json
```

**Expected Result:**
- Successfully parses structured datetime object with "+7d" offset
- Successfully parses "current_date" and "day_start" keywords
- CSV contains data for the 7-day forecast period

**Test with current_time keyword:**
```bash
aws lambda invoke \
  --function-name entso-scraper-lambda-demo \
  --cli-binary-format raw-in-base64-out \
  --payload file://tests/events/test-load.json \
  --region eu-central-1 \
  response-current-time.json

cat response-current-time.json
```

**Check logs for parsed timestamps:**
```bash
aws logs tail /aws/lambda/entso-scraper-lambda-demo \
  --region eu-central-1 \
  --since 5m \
  --filter-pattern "parameters_parsed"
```

---

## Test 4: EventBridge Scheduled Execution

Verify EventBridge rules are configured and can trigger Lambda.

**List EventBridge Rules:**
```bash
aws events list-rules \
  --name-prefix entso-scraper \
  --region eu-central-1
```

**Expected Output:**
- `entso-scraper-day-ahead-prices-cz-demo` - Daily at 2AM UTC
- `entso-scraper-actual-load-de-demo` - Every 6 hours
- `entso-scraper-generation-forecast-at-demo` - Daily at 6AM UTC

**Check Rule Details:**
```bash
aws events describe-rule \
  --name entso-scraper-day-ahead-prices-cz-demo \
  --region eu-central-1
```

**List Targets for Rule:**
```bash
aws events list-targets-by-rule \
  --rule entso-scraper-day-ahead-prices-cz-demo \
  --region eu-central-1
```

**Manually Trigger Lambda with EventBridge Payload:**

Use the test event files directly:
```bash
aws lambda invoke \
  --function-name entso-scraper-lambda-demo \
  --cli-binary-format raw-in-base64-out \
  --payload file://tests/events/test-day-ahead-prices.json \
  --region eu-central-1 \
  response-eventbridge.json
```

**Wait for Next Scheduled Execution:**

Check recent Lambda invocations:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=entso-scraper-lambda-demo \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --region eu-central-1
```

**Verify S3 Files from Scheduled Runs:**
```bash
aws s3 ls s3://entso-scraper-data-demo/ --recursive --region eu-central-1
```

Should see files created at scheduled times for all three rules.

---

## Test 5: Lambda Performance & Logs

Go to AWS Console -> Lambda -> entso-scraper-lambda-demo -> Monitor section for metrics and logs.


---

## Troubleshooting

### Lambda Timeout
- Check CloudWatch logs for timeout errors
- Verify VPC configuration allows internet access via fck-nat
- Increase timeout in `infra/terraform/modules/lambda/variables.tf` if needed

### API Rate Limiting
- Check CloudWatch logs for ENTSO-E API errors
- Adjust EventBridge schedule frequency

### Missing S3 Files
- Verify Lambda has S3 write permissions
- Check CloudWatch logs for S3 upload errors
- Verify bucket name matches deployed infrastructure

### Network Issues
- Verify fck-nat instance is running
- Check security group rules allow outbound HTTPS
- Verify private subnets route through NAT

---

## Success Criteria

### Unit Tests:
✅ **All unit tests pass:** 66 tests covering utils and lambda handler
✅ **Test coverage:** 94% overall (100% lambda_function.py, 93% utils.py)
✅ **No import errors:** All modules import correctly

### Integration Tests:
✅ **Test 1:** Lambda successfully invokes, CSV file created in S3, logs show no errors
✅ **Test 2:** Invalid method returns error, no S3 file created
✅ **Test 3:** Relative time parameters parsed correctly, data retrieved for correct period
✅ **Test 4:** EventBridge rules configured, Lambda invoked on schedule
✅ **Test 5:** No errors in CloudWatch metrics, execution time < 60s
