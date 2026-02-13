# EventBridge Rule 1: Day-Ahead Prices (CZ)
# Daily at 2:00 AM UTC
resource "aws_cloudwatch_event_rule" "day_ahead_prices_cz" {
  name        = "${var.project}-day-ahead-prices-cz-${var.environment}"
  description = "Fetch day-ahead electricity prices for Czech Republic"

  schedule_expression = "cron(0 2 * * ? *)"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_cloudwatch_event_target" "day_ahead_prices_cz" {
  rule      = aws_cloudwatch_event_rule.day_ahead_prices_cz.name
  target_id = "DayAheadPricesCZ"
  arn       = var.lambda_function_arn

  input = jsonencode({
    method_name = "query_day_ahead_prices"
    parameters = {
      country_code = "CZ"
      start = {
        date   = "current_date"
        time   = "day_start"
        offset = "-1d"
      }
      end = {
        date = "current_date"
        time = "day_start"
      }
      timezone = "Europe/Prague"
    }
  })
}

resource "aws_lambda_permission" "day_ahead_prices_cz" {
  statement_id  = "AllowEventBridgeDayAheadPricesCZ"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.day_ahead_prices_cz.arn
}

# EventBridge Rule 2: Actual Load (DE)
# Every 6 hours
resource "aws_cloudwatch_event_rule" "actual_load_de" {
  name        = "${var.project}-actual-load-de-${var.environment}"
  description = "Fetch actual electricity load for Germany"

  schedule_expression = "cron(0 */6 * * ? *)"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_cloudwatch_event_target" "actual_load_de" {
  rule      = aws_cloudwatch_event_rule.actual_load_de.name
  target_id = "ActualLoadDE"
  arn       = var.lambda_function_arn

  input = jsonencode({
    method_name = "query_load"
    parameters = {
      country_code = "DE"
      start = {
        date   = "current_date"
        time   = "current_time"
        offset = "-24h"
      }
      end = {
        date = "current_date"
        time = "current_time"
      }
      timezone = "Europe/Berlin"
    }
  })
}

resource "aws_lambda_permission" "actual_load_de" {
  statement_id  = "AllowEventBridgeActualLoadDE"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.actual_load_de.arn
}

# EventBridge Rule 3: Generation Forecast (AT)
# Daily at 6:00 AM UTC
resource "aws_cloudwatch_event_rule" "generation_forecast_at" {
  name        = "${var.project}-generation-forecast-at-${var.environment}"
  description = "Fetch generation forecast for Austria"

  schedule_expression = "cron(0 6 * * ? *)"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_cloudwatch_event_target" "generation_forecast_at" {
  rule      = aws_cloudwatch_event_rule.generation_forecast_at.name
  target_id = "GenerationForecastAT"
  arn       = var.lambda_function_arn

  input = jsonencode({
    method_name = "query_generation_forecast"
    parameters = {
      country_code = "AT"
      start = {
        date = "current_date"
        time = "day_start"
      }
      end = {
        date   = "current_date"
        time   = "day_start"
        offset = "+7d"
      }
      timezone = "Europe/Vienna"
    }
  })
}

resource "aws_lambda_permission" "generation_forecast_at" {
  statement_id  = "AllowEventBridgeGenerationForecastAT"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.generation_forecast_at.arn
}