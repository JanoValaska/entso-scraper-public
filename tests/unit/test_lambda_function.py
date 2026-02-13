"""
Unit tests for lambda_function.py

Tests cover:
- Lambda handler successful execution
- Lambda handler error handling
- DataFrame normalization from Series/DataFrame
"""

import json
import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from lambda_function import handler, to_timeseries_dataframe


class TestToTimeseriesDataframe:
    """Tests for to_timeseries_dataframe() function."""

    def test_convert_series_to_dataframe(self):
        """Test converting Series to DataFrame."""
        # Create a Series with datetime index
        index = pd.date_range("2026-02-10", periods=24, freq="h", tz="UTC")
        data = pd.Series(range(24), index=index, name="value")

        result = to_timeseries_dataframe(data, "query_test")

        assert isinstance(result, pd.DataFrame)
        assert result.index.name == "timestamp"
        assert "value" in result.columns
        assert len(result) == 24
        assert str(result.index.tz) == "UTC"

    def test_convert_series_without_name(self):
        """Test converting Series without name uses method name."""
        index = pd.date_range("2026-02-10", periods=24, freq="h", tz="UTC")
        data = pd.Series(range(24), index=index)

        result = to_timeseries_dataframe(data, "query_load")

        assert isinstance(result, pd.DataFrame)
        assert "query_load" in result.columns

    def test_convert_dataframe(self):
        """Test converting DataFrame."""
        index = pd.date_range("2026-02-10", periods=24, freq="h", tz="UTC")
        data = pd.DataFrame({"col1": range(24), "col2": range(24, 48)}, index=index)

        result = to_timeseries_dataframe(data, "query_test")

        assert isinstance(result, pd.DataFrame)
        assert result.index.name == "timestamp"
        assert "col1" in result.columns
        assert "col2" in result.columns
        assert len(result) == 24
        assert str(result.index.tz) == "UTC"

    def test_convert_series_naive_datetime_index(self):
        """Test converting Series with naive datetime index."""
        index = pd.date_range("2026-02-10", periods=24, freq="h")
        data = pd.Series(range(24), index=index, name="value")

        result = to_timeseries_dataframe(data, "query_test")

        assert isinstance(result, pd.DataFrame)
        assert str(result.index.tz) == "UTC"

    def test_convert_dataframe_naive_datetime_index(self):
        """Test converting DataFrame with naive datetime index."""
        index = pd.date_range("2026-02-10", periods=24, freq="h")
        data = pd.DataFrame({"col1": range(24)}, index=index)

        result = to_timeseries_dataframe(data, "query_test")

        assert isinstance(result, pd.DataFrame)
        assert str(result.index.tz) == "UTC"

    def test_convert_invalid_type(self):
        """Test converting invalid data type."""
        with pytest.raises(ValueError, match="returned invalid type"):
            to_timeseries_dataframe("not a series or dataframe", "query_test")

    def test_convert_series_sorts_index(self):
        """Test that Series is sorted by index."""
        # Create unsorted Series
        index = pd.date_range("2026-02-10", periods=24, freq="h", tz="UTC")
        data = pd.Series(range(24), index=index[::-1], name="value")  # Reverse order

        result = to_timeseries_dataframe(data, "query_test")

        assert result.index.is_monotonic_increasing

    def test_convert_dataframe_sorts_index(self):
        """Test that DataFrame is sorted by index."""
        # Create unsorted DataFrame
        index = pd.date_range("2026-02-10", periods=24, freq="h", tz="UTC")
        data = pd.DataFrame({"col1": range(24)}, index=index[::-1])

        result = to_timeseries_dataframe(data, "query_test")

        assert result.index.is_monotonic_increasing


class TestHandler:
    """Tests for Lambda handler function."""

    @patch("lambda_function.boto3.client")
    @patch("lambda_function.get_api_token")
    @patch("lambda_function.EntsoePandasClient")
    def test_handler_success(
        self, mock_client_class, mock_get_token, mock_boto3, monkeypatch
    ):
        """Test successful Lambda handler execution."""
        # Set environment
        monkeypatch.setenv("DATA_BUCKET_NAME", "test-bucket")

        # Mock API token
        mock_get_token.return_value = "test-token"

        # Mock EntsoePandasClient
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock method call to return Series
        index = pd.date_range("2026-02-10", periods=24, freq="h", tz="UTC")
        mock_data = pd.Series(range(24), index=index, name="price")
        mock_method = MagicMock(return_value=mock_data)
        mock_client.query_day_ahead_prices = mock_method

        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto3.return_value = mock_s3

        # Mock context
        mock_context = Mock()
        mock_context.aws_request_id = "test-request-id"

        # Test event
        event = {
            "method_name": "query_day_ahead_prices",
            "parameters": {
                "country_code": "CZ",
                "start": {"date": "2026-02-09", "time": "00:00:00"},
                "end": {"date": "2026-02-10", "time": "00:00:00"},
            },
        }

        # Execute handler
        response = handler(event, mock_context)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Data collection successful"
        assert body["method"] == "query_day_ahead_prices"
        assert "s3_location" in body

        # Verify S3 upload was called
        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert "query_day_ahead_prices" in call_args[1]["Key"]

    @patch("lambda_function.get_api_token")
    def test_handler_validation_error_missing_method(self, mock_get_token):
        """Test handler with validation error (missing method_name)."""
        mock_get_token.return_value = "test-token"
        mock_context = Mock()
        mock_context.aws_request_id = "test-request-id"

        event = {"parameters": {}}

        response = handler(event, mock_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "method_name" in body["error"]

    @patch("lambda_function.get_api_token")
    def test_handler_validation_error_invalid_method_prefix(self, mock_get_token):
        """Test handler with invalid method name (no query_ prefix)."""
        mock_get_token.return_value = "test-token"
        mock_context = Mock()
        mock_context.aws_request_id = "test-request-id"

        event = {
            "method_name": "get_day_ahead_prices",
            "parameters": {
                "country_code": "CZ",
                "start": {"date": "2026-02-09", "time": "00:00:00"},
                "end": {"date": "2026-02-10", "time": "00:00:00"},
            },
        }

        response = handler(event, mock_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "query_" in body["error"]

    @patch("lambda_function.get_api_token")
    @patch("lambda_function.EntsoePandasClient")
    def test_handler_method_not_found(self, mock_client_class, mock_get_token):
        """Test handler when method doesn't exist on client."""
        mock_get_token.return_value = "test-token"

        # Mock EntsoePandasClient without the method
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        del mock_client.query_nonexistent_method  # Ensure method doesn't exist

        mock_context = Mock()
        mock_context.aws_request_id = "test-request-id"

        event = {
            "method_name": "query_nonexistent_method",
            "parameters": {
                "country_code": "CZ",
                "start": {"date": "2026-02-09", "time": "00:00:00"},
                "end": {"date": "2026-02-10", "time": "00:00:00"},
            },
        }

        response = handler(event, mock_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    @patch("lambda_function.boto3.client")
    @patch("lambda_function.get_api_token")
    @patch("lambda_function.EntsoePandasClient")
    def test_handler_missing_bucket_env(
        self, mock_client_class, mock_get_token, mock_boto3, monkeypatch
    ):
        """Test handler with missing DATA_BUCKET_NAME environment variable."""
        # Remove environment variable
        monkeypatch.delenv("DATA_BUCKET_NAME", raising=False)

        mock_get_token.return_value = "test-token"

        # Mock EntsoePandasClient
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock method call
        index = pd.date_range("2026-02-10", periods=24, freq="h", tz="UTC")
        mock_data = pd.Series(range(24), index=index, name="price")
        mock_method = MagicMock(return_value=mock_data)
        mock_client.query_day_ahead_prices = mock_method

        mock_context = Mock()
        mock_context.aws_request_id = "test-request-id"

        event = {
            "method_name": "query_day_ahead_prices",
            "parameters": {
                "country_code": "CZ",
                "start": {"date": "2026-02-09", "time": "00:00:00"},
                "end": {"date": "2026-02-10", "time": "00:00:00"},
            },
        }

        response = handler(event, mock_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "DATA_BUCKET_NAME" in body["error"]

    @patch("lambda_function.boto3.client")
    @patch("lambda_function.get_api_token")
    @patch("lambda_function.EntsoePandasClient")
    def test_handler_s3_upload_failure(
        self, mock_client_class, mock_get_token, mock_boto3, monkeypatch
    ):
        """Test handler when S3 upload fails."""
        monkeypatch.setenv("DATA_BUCKET_NAME", "test-bucket")

        mock_get_token.return_value = "test-token"

        # Mock EntsoePandasClient
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock method call
        index = pd.date_range("2026-02-10", periods=24, freq="h", tz="UTC")
        mock_data = pd.Series(range(24), index=index, name="price")
        mock_method = MagicMock(return_value=mock_data)
        mock_client.query_day_ahead_prices = mock_method

        # Mock S3 client to raise exception
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = Exception("S3 upload failed")
        mock_boto3.return_value = mock_s3

        mock_context = Mock()
        mock_context.aws_request_id = "test-request-id"

        event = {
            "method_name": "query_day_ahead_prices",
            "parameters": {
                "country_code": "CZ",
                "start": {"date": "2026-02-09", "time": "00:00:00"},
                "end": {"date": "2026-02-10", "time": "00:00:00"},
            },
        }

        response = handler(event, mock_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body

    @patch("lambda_function.get_api_token")
    def test_handler_parameter_parsing_error(self, mock_get_token):
        """Test handler with invalid time parameters."""
        mock_get_token.return_value = "test-token"
        mock_context = Mock()
        mock_context.aws_request_id = "test-request-id"

        # Missing 'start' parameter
        event = {
            "method_name": "query_day_ahead_prices",
            "parameters": {
                "country_code": "CZ",
                "end": {"date": "2026-02-10", "time": "00:00:00"},
            },
        }

        response = handler(event, mock_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    @patch("lambda_function.boto3.client")
    @patch("lambda_function.get_api_token")
    @patch("lambda_function.EntsoePandasClient")
    def test_handler_with_dataframe_result(
        self, mock_client_class, mock_get_token, mock_boto3, monkeypatch
    ):
        """Test handler with DataFrame result (not Series)."""
        monkeypatch.setenv("DATA_BUCKET_NAME", "test-bucket")

        mock_get_token.return_value = "test-token"

        # Mock EntsoePandasClient
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock method call to return DataFrame
        index = pd.date_range("2026-02-10", periods=24, freq="h", tz="UTC")
        mock_data = pd.DataFrame(
            {"col1": range(24), "col2": range(24, 48)}, index=index
        )
        mock_method = MagicMock(return_value=mock_data)
        mock_client.query_generation_forecast = mock_method

        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto3.return_value = mock_s3

        mock_context = Mock()
        mock_context.aws_request_id = "test-request-id"

        event = {
            "method_name": "query_generation_forecast",
            "parameters": {
                "country_code": "AT",
                "start": {"date": "2026-02-09", "time": "00:00:00"},
                "end": {"date": "2026-02-10", "time": "00:00:00"},
            },
        }

        response = handler(event, mock_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Data collection successful"

        # Verify CSV was uploaded
        mock_s3.put_object.assert_called_once()
