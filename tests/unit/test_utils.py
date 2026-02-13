"""
Unit tests for utils.py

Tests cover:
- API token retrieval (SSM and environment variable)
- Datetime parsing (structured objects, keywords, offsets)
- Event parameter parsing and validation
- S3 key generation
- Parameter value sanitization
- Event validation
- Method name validation
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from utils import (
    format_datetime_utc_for_key,
    generate_s3_key,
    get_api_token,
    parse_datetime_object,
    parse_event_parameters,
    sanitize_parameter_value,
    validate_event,
    validate_method_name,
)


class TestGetApiToken:
    """Tests for get_api_token() function."""

    def test_get_token_from_environment(self, monkeypatch):
        """Test token retrieval from environment variable."""
        test_token = "test-env-token-12345"
        monkeypatch.setenv("ENTSO_API_TOKEN", test_token)

        token = get_api_token()

        assert token == test_token

    @patch("utils.boto3.client")
    def test_get_token_from_ssm(self, mock_boto3_client, monkeypatch):
        """Test token retrieval from SSM Parameter Store."""
        # Remove env variable to test SSM path
        monkeypatch.delenv("ENTSO_API_TOKEN", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "demo")

        # Mock SSM client
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "test-ssm-token-67890"}
        }
        mock_boto3_client.return_value = mock_ssm

        token = get_api_token()

        assert token == "test-ssm-token-67890"
        mock_ssm.get_parameter.assert_called_once_with(
            Name="/entso-scraper/demo/entso-api-token", WithDecryption=True
        )

    @patch("utils._cached_token", None)
    @patch("utils.boto3.client")
    def test_get_token_ssm_failure(self, mock_boto3_client, monkeypatch):
        """Test token retrieval failure from SSM."""
        monkeypatch.delenv("ENTSO_API_TOKEN", raising=False)

        # Mock SSM client to raise exception
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = Exception("Parameter not found")
        mock_boto3_client.return_value = mock_ssm

        with pytest.raises(ValueError, match="Failed to retrieve API token"):
            get_api_token()


class TestParseDatetimeObject:
    """Tests for parse_datetime_object() function."""

    def test_parse_current_date_day_start(self):
        """Test parsing current_date with day_start."""
        obj = {"date": "current_date", "time": "day_start"}

        result = parse_datetime_object(obj, "UTC")

        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_parse_current_date_day_end(self):
        """Test parsing current_date with day_end."""
        obj = {"date": "current_date", "time": "day_end"}

        result = parse_datetime_object(obj, "UTC")

        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"
        # day_end is next midnight
        assert result.hour == 0
        assert result.minute == 0

    def test_parse_current_date_current_time(self):
        """Test parsing current_date with current_time."""
        obj = {"date": "current_date", "time": "current_time"}

        result = parse_datetime_object(obj, "UTC")

        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"

    def test_parse_explicit_date_and_time(self):
        """Test parsing explicit ISO date with HH:MM time."""
        obj = {"date": "2026-02-10", "time": "14:30:00"}

        result = parse_datetime_object(obj, "UTC")

        assert isinstance(result, pd.Timestamp)
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 10
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 0
        assert str(result.tz) == "UTC"

    def test_parse_with_negative_day_offset(self):
        """Test parsing with -1d offset."""
        obj = {"date": "current_date", "time": "day_start", "offset": "-1d"}

        result = parse_datetime_object(obj, "UTC")

        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"
        # Should be 1 day before current date at midnight

    def test_parse_with_positive_day_offset(self):
        """Test parsing with +7d offset."""
        obj = {"date": "current_date", "time": "day_start", "offset": "+7d"}

        result = parse_datetime_object(obj, "UTC")

        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"

    def test_parse_with_hour_offset(self):
        """Test parsing with -6h offset."""
        obj = {"date": "current_date", "time": "current_time", "offset": "-6h"}

        result = parse_datetime_object(obj, "UTC")

        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"

    def test_parse_with_minute_offset(self):
        """Test parsing with +30m offset."""
        obj = {"date": "current_date", "time": "current_time", "offset": "+30m"}

        result = parse_datetime_object(obj, "UTC")

        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"

    def test_parse_with_timezone(self):
        """Test parsing with non-UTC timezone."""
        obj = {"date": "2026-02-10", "time": "12:00:00"}

        result = parse_datetime_object(obj, "Europe/Prague")

        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"
        # Should be converted to UTC

    def test_parse_invalid_date_token(self):
        """Test parsing with invalid date token."""
        obj = {"date": "invalid_date", "time": "day_start"}

        with pytest.raises(ValueError, match="Invalid date token"):
            parse_datetime_object(obj, "UTC")

    def test_parse_invalid_time_token(self):
        """Test parsing with invalid time token."""
        obj = {"date": "current_date", "time": "invalid_time"}

        with pytest.raises(ValueError, match="Invalid time token"):
            parse_datetime_object(obj, "UTC")

    def test_parse_invalid_offset(self):
        """Test parsing with invalid offset."""
        obj = {"date": "current_date", "time": "day_start", "offset": "invalid"}

        with pytest.raises(ValueError, match="Invalid offset"):
            parse_datetime_object(obj, "UTC")

    def test_parse_missing_date(self):
        """Test parsing without date field."""
        obj = {"time": "day_start"}

        with pytest.raises(ValueError, match="must contain 'date' and 'time'"):
            parse_datetime_object(obj, "UTC")

    def test_parse_missing_time(self):
        """Test parsing without time field."""
        obj = {"date": "current_date"}

        with pytest.raises(ValueError, match="must contain 'date' and 'time'"):
            parse_datetime_object(obj, "UTC")

    def test_parse_not_dict(self):
        """Test parsing with non-dict input."""
        with pytest.raises(ValueError, match="Expected dict"):
            parse_datetime_object("not a dict", "UTC")


class TestParseEventParameters:
    """Tests for parse_event_parameters() function."""

    def test_parse_valid_parameters(self):
        """Test parsing valid event parameters."""
        parameters = {
            "country_code": "CZ",
            "start": {"date": "current_date", "time": "day_start", "offset": "-1d"},
            "end": {"date": "current_date", "time": "day_start"},
            "timezone": "Europe/Prague",
        }

        result = parse_event_parameters(parameters)

        assert "country_code" in result
        assert result["country_code"] == "CZ"
        assert "start" in result
        assert "end" in result
        assert isinstance(result["start"], pd.Timestamp)
        assert isinstance(result["end"], pd.Timestamp)
        assert "timezone" not in result  # timezone should not be in output

    def test_parse_missing_start(self):
        """Test parsing without start parameter."""
        parameters = {
            "country_code": "DE",
            "end": {"date": "current_date", "time": "day_start"},
        }

        with pytest.raises(ValueError, match="must contain both 'start' and 'end'"):
            parse_event_parameters(parameters)

    def test_parse_missing_end(self):
        """Test parsing without end parameter."""
        parameters = {
            "country_code": "DE",
            "start": {"date": "current_date", "time": "day_start"},
        }

        with pytest.raises(ValueError, match="must contain both 'start' and 'end'"):
            parse_event_parameters(parameters)

    def test_parse_start_not_dict(self):
        """Test parsing with start not being a dict."""
        parameters = {
            "country_code": "DE",
            "start": "not a dict",
            "end": {"date": "current_date", "time": "day_start"},
        }

        with pytest.raises(ValueError, match="must be structured datetime objects"):
            parse_event_parameters(parameters)

    def test_parse_end_before_start(self):
        """Test parsing with end before start."""
        parameters = {
            "country_code": "DE",
            "start": {"date": "current_date", "time": "day_start"},
            "end": {"date": "current_date", "time": "day_start", "offset": "-1d"},
        }

        with pytest.raises(ValueError, match="end.*must be after start"):
            parse_event_parameters(parameters)

    def test_parse_with_default_timezone(self):
        """Test parsing with default UTC timezone."""
        parameters = {
            "country_code": "AT",
            "start": {"date": "current_date", "time": "day_start"},
            "end": {"date": "current_date", "time": "day_end"},
        }

        result = parse_event_parameters(parameters)

        assert isinstance(result["start"], pd.Timestamp)
        assert isinstance(result["end"], pd.Timestamp)

    def test_parse_preserves_other_parameters(self):
        """Test that other parameters are preserved."""
        parameters = {
            "country_code": "CZ",
            "start": {"date": "current_date", "time": "day_start"},
            "end": {"date": "current_date", "time": "day_end"},
            "extra_param": "extra_value",
        }

        result = parse_event_parameters(parameters)

        assert result["extra_param"] == "extra_value"


class TestSanitizeParameterValue:
    """Tests for sanitize_parameter_value() function."""

    def test_sanitize_string_with_colons(self):
        """Test sanitizing string with colons."""
        result = sanitize_parameter_value("12:30:00")
        assert result == "12-30-00"

    def test_sanitize_string_with_slashes(self):
        """Test sanitizing string with slashes."""
        result = sanitize_parameter_value("2026/02/10")
        assert result == "2026-02-10"

    def test_sanitize_string_with_spaces(self):
        """Test sanitizing string with spaces."""
        result = sanitize_parameter_value("some value")
        assert result == "some-value"

    def test_sanitize_timestamp(self):
        """Test sanitizing pandas Timestamp."""
        ts = pd.Timestamp("2026-02-10 14:30:00", tz="UTC")
        result = sanitize_parameter_value(ts)
        assert result == "20260210T143000Z"

    def test_sanitize_datetime(self):
        """Test sanitizing datetime object."""
        dt = datetime(2026, 2, 10, 14, 30, 0)
        result = sanitize_parameter_value(dt)
        assert result == "20260210T143000Z"

    def test_sanitize_removes_special_chars(self):
        """Test that special characters are removed."""
        result = sanitize_parameter_value("test@#$%value")
        assert result == "testvalue"

    def test_sanitize_preserves_alphanumeric(self):
        """Test that alphanumeric and dash/underscore are preserved."""
        result = sanitize_parameter_value("test_value-123")
        assert result == "test_value-123"


class TestGenerateS3Key:
    """Tests for generate_s3_key() function."""

    def test_generate_key_basic(self):
        """Test basic S3 key generation."""
        method_name = "query_day_ahead_prices"
        parameters = {
            "country_code": "CZ",
            "start": pd.Timestamp("2026-02-09 00:00:00", tz="UTC"),
            "end": pd.Timestamp("2026-02-10 00:00:00", tz="UTC"),
        }

        key = generate_s3_key(method_name, parameters)

        assert key.startswith("query_day_ahead_prices/")
        assert "country_code_CZ" in key
        assert "start_20260209T000000Z" in key
        assert "end_20260210T000000Z" in key
        assert "created_" in key
        assert key.endswith(".csv")

    def test_generate_key_with_param_order(self):
        """Test S3 key generation with parameter order."""
        method_name = "query_load"
        parameters = {
            "country_code": "DE",
            "start": pd.Timestamp("2026-02-09 00:00:00", tz="UTC"),
            "end": pd.Timestamp("2026-02-10 00:00:00", tz="UTC"),
        }
        param_order = ["country_code", "start", "end"]

        key = generate_s3_key(method_name, parameters, param_order)

        assert key.startswith("query_load/")
        # Check order: country_code comes first
        assert key.index("country_code") < key.index("start")
        assert key.index("start") < key.index("end")

    def test_generate_key_alphabetical_order(self):
        """Test S3 key generation uses alphabetical order without param_order."""
        method_name = "query_test"
        parameters = {"zebra": "z", "alpha": "a", "beta": "b"}

        key = generate_s3_key(method_name, parameters)

        # Without param_order, should be alphabetical
        assert key.index("alpha") < key.index("beta")
        assert key.index("beta") < key.index("zebra")

    def test_generate_key_with_special_chars(self):
        """Test S3 key generation sanitizes special characters."""
        method_name = "query_test"
        parameters = {"param1": "value:with/special chars"}

        key = generate_s3_key(method_name, parameters)

        assert ":" not in key
        assert "/" not in key.split("/", 1)[1]  # No slashes after method name


class TestFormatDatetimeUtcForKey:
    """Tests for format_datetime_utc_for_key() function."""

    def test_format_timestamp_utc(self):
        """Test formatting UTC timestamp."""
        ts = pd.Timestamp("2026-02-10 14:30:15", tz="UTC")
        result = format_datetime_utc_for_key(ts)
        assert result == "20260210T143015Z"

    def test_format_timestamp_with_tz_conversion(self):
        """Test formatting timestamp with timezone conversion."""
        ts = pd.Timestamp("2026-02-10 14:30:15", tz="Europe/Prague")
        result = format_datetime_utc_for_key(ts)
        # Should be converted to UTC
        assert result.endswith("Z")

    def test_format_datetime(self):
        """Test formatting datetime object."""
        dt = datetime(2026, 2, 10, 14, 30, 15)
        result = format_datetime_utc_for_key(dt)
        assert result == "20260210T143015Z"

    def test_format_invalid_type(self):
        """Test formatting with invalid type."""
        with pytest.raises(TypeError, match="Unsupported type"):
            format_datetime_utc_for_key("not a datetime")


class TestValidateEvent:
    """Tests for validate_event() function."""

    def test_validate_valid_event(self):
        """Test validation of valid event."""
        event = {
            "method_name": "query_day_ahead_prices",
            "parameters": {"country_code": "CZ"},
        }

        # Should not raise
        validate_event(event)

    def test_validate_not_dict(self):
        """Test validation with non-dict event."""
        with pytest.raises(ValueError, match="Event must be a dictionary"):
            validate_event("not a dict")

    def test_validate_missing_method_name(self):
        """Test validation with missing method_name."""
        event = {"parameters": {}}

        with pytest.raises(ValueError, match="missing required field: 'method_name'"):
            validate_event(event)

    def test_validate_missing_parameters(self):
        """Test validation with missing parameters."""
        event = {"method_name": "query_test"}

        with pytest.raises(ValueError, match="missing required field: 'parameters'"):
            validate_event(event)

    def test_validate_method_name_not_string(self):
        """Test validation with non-string method_name."""
        event = {"method_name": 123, "parameters": {}}

        with pytest.raises(ValueError, match="'method_name' must be a string"):
            validate_event(event)

    def test_validate_parameters_not_dict(self):
        """Test validation with non-dict parameters."""
        event = {"method_name": "query_test", "parameters": "not a dict"}

        with pytest.raises(ValueError, match="'parameters' must be a dictionary"):
            validate_event(event)


class TestValidateMethodName:
    """Tests for validate_method_name() function."""

    def test_validate_valid_method_name(self):
        """Test validation of valid method name."""
        # Should not raise
        validate_method_name("query_day_ahead_prices")
        validate_method_name("query_load")
        validate_method_name("query_generation_forecast")

    def test_validate_invalid_method_name(self):
        """Test validation of invalid method name."""
        with pytest.raises(ValueError, match="Only methods starting with 'query_'"):
            validate_method_name("get_day_ahead_prices")

    def test_validate_method_name_without_prefix(self):
        """Test validation of method name without query_ prefix."""
        with pytest.raises(ValueError, match="Only methods starting with 'query_'"):
            validate_method_name("day_ahead_prices")

    def test_validate_empty_method_name(self):
        """Test validation of empty method name."""
        with pytest.raises(ValueError, match="Only methods starting with 'query_'"):
            validate_method_name("")
