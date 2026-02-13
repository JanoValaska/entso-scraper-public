"""
ENTSO-E Data Collection Lambda Handler

This Lambda function dynamically invokes entsoe-py EntsoePandasClient methods
based on EventBridge event payloads. It supports flexible time parameter parsing,
stores results in S3 as CSV, and is fully config-driven (no code changes needed
to add new data sources).

Event Payload Schema:
{
    "method_name": "query_day_ahead_prices",
    "parameters": {
        "country_code": "CZ",
        "start": "-1d",
        "end": "today"
    }
}

References:
- SPEC.md: Functional requirements FR1-FR6
- ARCHITECTURE.md: System design and security
"""

import inspect
import json
import logging
import os
from io import StringIO
from typing import Any, Dict

import boto3
from entsoe import EntsoePandasClient
import pandas as pd

from utils import (
    generate_s3_key,
    get_api_token,
    parse_event_parameters,
    validate_event,
    validate_method_name,
)

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# CSV export format
CSV_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  # ISO 8601 UTC format


def to_timeseries_dataframe(data: Any, method_name: str) -> pd.DataFrame:
    """
    Normalize entsoe-py output (Series/DataFrame) into a DataFrame with:
    - sorted DatetimeIndex
    - timezone normalized to UTC where possible
    - index named 'timestamp'
    - Series gets a meaningful value column name
    """
    if isinstance(data, pd.Series):
        s = data.sort_index()

        # Ensure the values column has a stable name
        value_col = s.name or method_name

        # Normalize timezone on the index (best-effort)
        if isinstance(s.index, pd.DatetimeIndex):
            if s.index.tz is None:
                logger.warning(
                    json.dumps(
                        {
                            "event_type": "naive_datetime_index_detected",
                            "message": "Series index has no timezone; localizing to UTC.",
                            "method_name": method_name,
                        }
                    )
                )
                s.index = s.index.tz_localize("UTC")
            else:
                s = s.tz_convert("UTC")

        df = s.rename(value_col).to_frame()

    elif isinstance(data, pd.DataFrame):
        df = data.sort_index()

        if isinstance(df.index, pd.DatetimeIndex):
            if df.index.tz is None:
                logger.warning(
                    json.dumps(
                        {
                            "event_type": "naive_datetime_index_detected",
                            "message": "DataFrame index has no timezone; localizing to UTC.",
                            "method_name": method_name,
                        }
                    )
                )
                df.index = df.index.tz_localize("UTC")
            else:
                df = df.tz_convert("UTC")
    else:
        raise ValueError(
            f"EntsoePandasClient.{method_name} returned invalid type: {type(data)}"
        )

    df.index.name = "timestamp"
    return df


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for ENTSO-E data collection.

    Args:
        event: EventBridge event payload with method_name and parameters
        context: Lambda context object

    Returns:
        Response dict with statusCode and body

    Raises:
        ValueError: If event validation fails
        AttributeError: If method doesn't exist on EntsoePandasClient
    """
    try:
        # 1. Log invocation
        logger.info(
            json.dumps(
                {
                    "event_type": "lambda_invocation",
                    "method_name": event.get("method_name"),
                    "parameters": event.get("parameters"),
                    "request_id": context.aws_request_id if context else None,
                }
            )
        )

        # 2. Validate event structure
        validate_event(event)
        method_name = event["method_name"]
        parameters = event["parameters"]

        # 3. Validate method name (must start with 'query_')
        validate_method_name(method_name)

        # 4. Retrieve API token from SSM (with caching)
        api_token = get_api_token()
        logger.info(
            json.dumps(
                {"event_type": "token_retrieved", "source": "SSM or environment"}
            )
        )

        # 5. Parse time parameters (relative → absolute)
        parsed_parameters = parse_event_parameters(parameters)
        logger.info(
            json.dumps(
                {
                    "event_type": "parameters_parsed",
                    "original_parameters": parameters,
                    "parsed_parameters": {
                        k: str(v) for k, v in parsed_parameters.items()
                    },
                }
            )
        )

        # 6. Initialize ENTSO-E client
        client = EntsoePandasClient(api_key=api_token)

        # 7. Dynamic method invocation
        if not hasattr(client, method_name):
            raise AttributeError(
                f"Method '{method_name}' does not exist on EntsoePandasClient"
            )

        method = getattr(client, method_name)
        logger.info(
            json.dumps(
                {"event_type": "method_execution_start", "method_name": method_name}
            )
        )

        # 8. Execute method
        data = method(**parsed_parameters)

        # Normalize result to a DataFrame that preserves the time index
        dataframe = to_timeseries_dataframe(data, method_name)

        # 9. Log DataFrame info
        logger.info(
            json.dumps(
                {
                    "event_type": "dataframe_retrieved",
                    "shape": dataframe.shape,
                    "columns": list(dataframe.columns),
                }
            )
        )

        # 10. Convert DataFrame to CSV
        csv_buffer = StringIO()
        dataframe.to_csv(
            csv_buffer,
            index=True,                      # keep timestamps (index)
            index_label="timestamp",         # first column header
            date_format=CSV_TIMESTAMP_FORMAT # ISO-like UTC format
        )
        csv_content = csv_buffer.getvalue()

        # 11. Generate S3 key
        s3_bucket = os.environ.get("DATA_BUCKET_NAME")
        if not s3_bucket:
            raise ValueError("DATA_BUCKET_NAME environment variable not set")

        param_order = list(inspect.signature(method).parameters.keys())
        s3_key = generate_s3_key(
            method_name, parsed_parameters, param_order=param_order
        )

        # 12. Upload to S3
        s3_client = boto3.client("s3")
        s3_client.put_object(Bucket=s3_bucket, Key=s3_key, Body=csv_content)

        logger.info(
            json.dumps(
                {
                    "event_type": "s3_upload_success",
                    "bucket": s3_bucket,
                    "key": s3_key,
                    "size_bytes": len(csv_content),
                }
            )
        )

        # 13. Return success
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Data collection successful",
                    "method": method_name,
                    "s3_location": f"s3://{s3_bucket}/{s3_key}",
                }
            ),
        }

    except ValueError as e:
        # Validation errors
        logger.error(
            json.dumps(
                {
                    "level": "ERROR",
                    "error_type": "ValidationError",
                    "error": str(e),
                    "method_name": event.get("method_name"),
                    "parameters": event.get("parameters"),
                }
            )
        )
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    except AttributeError as e:
        # Method not found
        logger.error(
            json.dumps(
                {
                    "level": "ERROR",
                    "error_type": "MethodNotFound",
                    "error": str(e),
                    "method_name": event.get("method_name"),
                }
            )
        )
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    except Exception as e:
        # All other errors
        logger.error(
            json.dumps(
                {
                    "level": "ERROR",
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "method_name": event.get("method_name"),
                    "parameters": event.get("parameters"),
                }
            ),
            exc_info=True,
        )
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal error: {str(e)}"}),
        }
