"""
Utility functions for ENTSO-E data collection Lambda.

Provides:
- API token retrieval (SSM with caching + local env fallback)
- Time parameter parsing (relative and absolute)
- S3 key generation
- Event validation

References:
- SPEC.md: FR5 (Time parsing), FR2 (S3 key structure)
- ARCHITECTURE.md: Token access pattern
- DECISIONS.md: D5, D6, D7, D9
"""

import os
import re
import json
import logging
from datetime import datetime, UTC

from typing import Any

import boto3
import pandas as pd

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# CSV export format
CSV_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  # ISO 8601 UTC format

# Global cache for API token (survives warm Lambda invocations)
_cached_token = None


def get_api_token() -> str:
    """
    Retrieve ENTSO-E API token with hybrid approach:
    - Production: Read from SSM Parameter Store (with caching)
    - Development: Fallback to ENTSO_API_TOKEN environment variable

    Returns:
        API token string

    Raises:
        ValueError: If token cannot be retrieved

    References:
        - ARCHITECTURE.md: Section 5 (Token Management)
        - DECISIONS.md: D26 (Token access pattern)
    """
    global _cached_token

    # Local development: use environment variable
    if "ENTSO_API_TOKEN" in os.environ:
        return os.environ["ENTSO_API_TOKEN"]

    # Production: read from SSM (with caching)
    if _cached_token is not None:
        return _cached_token

    env = os.environ.get("ENVIRONMENT")
    if not env:
        raise ValueError("ENVIRONMENT is not set; cannot build SSM parameter name.")

    parameter_name = f"/entso-scraper/{env}/entso-api-token"

    try:
        ssm = boto3.client("ssm")
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
        _cached_token = response["Parameter"]["Value"]
        return _cached_token
    except Exception as e:
        raise ValueError(
            f"Failed to retrieve API token from SSM ({parameter_name}): {str(e)}"
        )


# Structured datetime parsing rules (new format only)
#
# start/end must be dict objects with:
#   {
#     "date": "current_date" | "YYYY-MM-DD",
#     "time": "current_time" | "day_start" | "day_end" | "HH:MM[:SS]",
#     "offset": "+/-{number}{unit}"   # optional, unit m/h/d/w/M
#   }
#
# timezone is optional in event parameters; defaults to UTC if not present.
# timezone is used only for parsing (NOT returned in parsed kwargs).


_RELATIVE_PATTERN = re.compile(r"^([+-]?)(\d+)([mhdwM])$", re.IGNORECASE)
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_PATTERN = re.compile(r"^(\d{2}):(\d{2})(?::(\d{2}))?$")


def _now_in_tz(timezone: str) -> pd.Timestamp:
    """
    Get current timestamp in provided timezone, floored to whole seconds.
    """
    try:
        ts = pd.Timestamp.now(tz=timezone)
        try:
            # Some pandas versions require lowercase "s"
            return ts.floor("s")
        except Exception:
            # Fallback: remove microseconds
            return ts.replace(microsecond=0)
    except Exception as e:
        raise ValueError(f"Invalid timezone '{timezone}': {str(e)}")


def _to_utc(ts: pd.Timestamp) -> pd.Timestamp:
    """
    Convert timezone-aware Timestamp to UTC. If tz-naive, localize to UTC.
    """
    if ts.tz is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def format_datetime_utc_for_key(value: pd.Timestamp | datetime) -> str:
    """
    Format a datetime-like value as a filename-safe UTC string.

    Output example: 20260209T211116Z
    """
    if isinstance(value, pd.Timestamp):
        ts = value
    elif isinstance(value, datetime):
        ts = pd.Timestamp(value)
    else:
        raise TypeError(f"Unsupported type for datetime formatting: {type(value)}")

    if ts.tz is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")

    return ts.strftime("%Y%m%dT%H%M%SZ")


def _apply_offset(base: pd.Timestamp, offset: str) -> pd.Timestamp:
    """
    Apply an offset like -1d, +6h, +30m, +1w, +1M to a base timestamp.
    """
    _match = _RELATIVE_PATTERN.match(offset.strip())
    if not _match:
        raise ValueError(
            f"Invalid offset '{offset}'. Supported: '+/-{{number}}{{unit}}' where unit is m/h/d/w/M."
        )

    sign, number, unit = _match.groups()
    number_i = int(number)
    if sign == "-":
        number_i = -number_i

    if unit == "M":
        # months (calendar-based)
        from pandas.tseries.offsets import DateOffset

        return base + DateOffset(months=number_i)

    unit_map = {
        "m": "minutes",
        "h": "hours",
        "d": "days",
        "w": "weeks",
    }
    delta = pd.Timedelta(**{unit_map[unit.lower()]: number_i})
    return base + delta


def _resolve_date_token(date_token: str, timezone: str) -> pd.Timestamp:
    """
    Resolve date token to a timezone-aware Timestamp at midnight (start of that date).

    Supported:
    - current_date
    - YYYY-MM-DD
    """
    raw_token = date_token.strip()

    if raw_token.lower() == "current_date":
        return _now_in_tz(timezone).normalize()

    if _ISO_DATE_PATTERN.match(raw_token):
        # Interpret explicit date in provided timezone at midnight
        naive = pd.Timestamp(raw_token)
        try:
            # Midnight is typically safe, but keep strict DST handling.
            return naive.tz_localize(
                timezone, ambiguous="raise", nonexistent="raise"
            ).normalize()
        except TypeError:
            # Compatibility with pandas versions that don't accept ambiguous/nonexistent args
            return naive.tz_localize(timezone).normalize()

    raise ValueError(
        f"Invalid date token '{date_token}'. Supported: 'current_date' or ISO date 'YYYY-MM-DD'."
    )


def _resolve_time_token(
    time_token: str, date_start: pd.Timestamp, timezone: str
) -> pd.Timestamp:
    """
    Resolve time token into a base datetime.

    Supported:
    - current_time: uses current time-of-day in timezone, applied to date_start
    - day_start: midnight at date_start
    - day_end: next midnight (end-exclusive boundary)
    - HH:MM[:SS]

    Returns (is_day_end, timestamp):
      - if is_day_end=True, timestamp is next midnight for the given date
      - otherwise, timestamp is date_start + time-of-day
    """

    token = time_token.strip().lower()

    if token == "current_time":
        now = _now_in_tz(timezone)
        tod = now - now.normalize()
        return date_start + tod

    if token == "day_start":
        return date_start

    if token == "day_end":
        # Next midnight (recommended for half-open ranges)
        return date_start + pd.Timedelta(days=1)

    _match = _TIME_PATTERN.match(time_token.strip())
    if not _match:
        raise ValueError(
            f"Invalid time token '{time_token}'. Supported: 'current_time', 'day_start', "
            f"'day_end', or 'HH:MM[:SS]'."
        )

    hh, mm, ss = _match.groups()
    h = int(hh)
    m = int(mm)
    s = int(ss) if ss is not None else 0

    if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
        raise ValueError(
            f"Invalid time value '{time_token}'. Must be HH:MM[:SS] within valid ranges."
        )

    return date_start + pd.Timedelta(hours=h, minutes=m, seconds=s)


def parse_datetime_object(obj: dict[str, Any], timezone: str) -> pd.Timestamp:
    """
    Parse structured datetime object:
      {
        "date": "current_date" | "YYYY-MM-DD",
        "time": "current_time" | "day_start" | "day_end" | "HH:MM[:SS]",
        "offset": "+/-{number}{unit}"   # optional, m/h/d/w/M
      }

    Args:
        obj: Structured datetime object
        timezone: Timezone used to interpret date/time tokens

    Returns:
        pandas Timestamp in UTC

    Raises:
        ValueError: If object format is invalid or tokens are invalid

    References:
        - SPEC.md: FR5 (Time Parameter Parsing)
        - DECISIONS.md: D5, D6, D7
    """
    if not isinstance(obj, dict):
        raise ValueError(f"Expected dict for datetime object, got {type(obj)}")

    if "date" not in obj or "time" not in obj:
        raise ValueError("Datetime object must contain 'date' and 'time' fields")

    date_start = _resolve_date_token(str(obj["date"]), timezone)
    base = _resolve_time_token(str(obj["time"]), date_start, timezone)

    # Apply offset last (optional)
    offset = obj.get("offset")
    if offset is not None and str(offset).strip() != "":
        base = _apply_offset(base, str(offset))

    return _to_utc(base)


def parse_event_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    """
    Parse all parameters in event, converting structured start/end to UTC Timestamps.

    Supported:
    - timezone: optional; defaults to UTC
    - start: required structured datetime object (dict)
    - end: required structured datetime object (dict)

    Other parameters are passed through unchanged.

    Args:
        parameters: Raw parameters from event payload

    Returns:
        Parsed parameters with start/end converted to UTC pandas Timestamps.
        'timezone' is NOT returned (it is only used for parsing).

    Raises:
        ValueError: If required parameters are missing or invalid.

    References:
        - SPEC.md: FR5 (Time Parameter Parsing)
    """
    timezone = str(parameters.get("timezone") or "UTC")
    # validate timezone early
    _ = _now_in_tz(timezone)

    parsed: dict[str, Any] = {}

    # Check expected params
    if "start" not in parameters or "end" not in parameters:
        raise ValueError(
            "Parameters must contain both 'start' and 'end' as structured datetime objects"
        )

    start_val = parameters["start"]
    end_val = parameters["end"]

    if not isinstance(start_val, dict) or not isinstance(end_val, dict):
        raise ValueError(
            "'start' and 'end' must be structured datetime objects (dicts)"
        )

    parsed["start"] = parse_datetime_object(start_val, timezone)
    parsed["end"] = parse_datetime_object(end_val, timezone)

    # Optional safety check: ensure start < end
    if parsed["end"] <= parsed["start"]:
        raise ValueError(
            f"Invalid time range: end ({parsed['end']}) must be after start ({parsed['start']})."
        )

    # Parse the rest of the parameters (do not pass timezone through)
    for key, value in parameters.items():
        if key in ("start", "end", "timezone"):
            continue
        parsed[key] = value

    return parsed


def sanitize_parameter_value(value: Any) -> str:
    """
    Sanitize parameter value for S3 key.

    Replaces special characters that are problematic in S3 keys:
    - ':' → '-'
    - '/' → '-'
    - ' ' → '-'
    - Other special chars removed or replaced

    Args:
        value: Parameter value (any type)

    Returns:
        Sanitized string safe for S3 keys

    References:
        - SPEC.md: FR2 (S3 Key Generation Rules)
    """
    if isinstance(value, (pd.Timestamp, datetime)):
        value_str = format_datetime_utc_for_key(value)
    else:
        value_str = str(value)

    # Replace problematic characters
    sanitized = value_str.replace(":", "-").replace("/", "-").replace(" ", "-")
    # Remove any remaining special chars except alphanumeric, dash, underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", sanitized)
    return sanitized


def generate_s3_key(
    method_name: str,
    parameters: dict[str, Any],
    param_order: list[str] | None = None,
) -> str:
    """
    Generate S3 key from method name and parameters.

    Format: {method_name}/{encoded_params}__created_{timestamp}.csv

    If param_order is provided, parameters are placed in that order first,
    then any remaining parameters are appended alphabetically.
    """
    # Build an ordered list of (key, value)
    items: list[tuple[str, Any]] = []

    if param_order:
        # add keys in signature order if present
        for k in param_order:
            if k in parameters:
                items.append((k, parameters[k]))

        # append any extras not in signature, sorted for stability
        extras = sorted(
            (k, v) for k, v in parameters.items() if k not in set(param_order)
        )
        items.extend(extras)
    else:
        # default: stable alphabetical
        items = sorted(parameters.items())

    # Encode parameters as key_value__ format
    param_parts = []
    for key, value in items:
        sanitized_value = sanitize_parameter_value(value)
        param_parts.append(f"{key}_{sanitized_value}")

    # Join with double underscore
    params_encoded = "__".join(param_parts)

    # Generate timestamp (execution time, not data time)
    timestamp = format_datetime_utc_for_key(datetime.now(UTC))

    # Construct full key (created_ prefix)
    filename = f"{params_encoded}__created_{timestamp}.csv"
    s3_key = f"{method_name}/{filename}"

    return s3_key


def validate_event(event: dict[str, Any]) -> None:
    """
    Validate EventBridge event structure.

    Required fields:
    - method_name (str)
    - parameters (dict)

    Args:
        event: Event payload

    Raises:
        ValueError: If event structure is invalid

    References:
        - SPEC.md: FR4 (Event Payload Schema)
    """
    if not isinstance(event, dict):
        raise ValueError("Event must be a dictionary")

    if "method_name" not in event:
        raise ValueError("Event missing required field: 'method_name'")

    if "parameters" not in event:
        raise ValueError("Event missing required field: 'parameters'")

    if not isinstance(event["method_name"], str):
        raise ValueError("Field 'method_name' must be a string")

    if not isinstance(event["parameters"], dict):
        raise ValueError("Field 'parameters' must be a dictionary")


def validate_method_name(method_name: str) -> None:
    """
    Validate that method name starts with 'query_' prefix.

    This is a security boundary to prevent calling internal or dangerous methods.

    Args:
        method_name: Name of method to invoke

    Raises:
        ValueError: If method name doesn't start with 'query_'

    References:
        - SPEC.md: FR1 (Method Validation)
        - DECISIONS.md: D4 (Method validation security)
    """
    if not method_name.startswith("query_"):
        raise ValueError(
            f"Invalid method name '{method_name}'. "
            f"Only methods starting with 'query_' are allowed."
        )

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