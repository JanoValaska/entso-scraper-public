############################################
# EventBridge Scheduler
############################################

data "aws_caller_identity" "current" {}

# Execution role assumed by EventBridge Scheduler to invoke Lambda
resource "aws_iam_role" "scheduler_invoke_lambda" {
  name = "${var.project}-scheduler-invoke-lambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = { Service = "scheduler.amazonaws.com" },
        Action = "sts:AssumeRole",
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_iam_role_policy" "scheduler_invoke_lambda" {
  name = "${var.project}-scheduler-invoke-lambda-${var.environment}"
  role = aws_iam_role.scheduler_invoke_lambda.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = ["lambda:InvokeFunction"],
        Resource = [
          var.lambda_function_arn,
          "${var.lambda_function_arn}:*"
        ]
      }
    ]
  })
}

resource "aws_scheduler_schedule_group" "this" {
  name = "${var.project}-${var.environment}"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

############################################
# Schedule 1: Day-Ahead Prices (CZ)
# Daily at 02:00 UTC
############################################
resource "aws_scheduler_schedule" "day_ahead_prices_cz" {
  name        = "${var.project}-day-ahead-prices-cz-${var.environment}"
  description = "Fetch day-ahead electricity prices for Czech Republic"

  group_name = aws_scheduler_schedule_group.this.name

  # Required by aws_scheduler_schedule
  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 2 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = var.lambda_function_arn
    role_arn = aws_iam_role.scheduler_invoke_lambda.arn
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
}

############################################
# Schedule 2: Actual Load (DE)
# Every 6 hours (aligned to minute 0)
############################################
resource "aws_scheduler_schedule" "actual_load_de" {
  name        = "${var.project}-actual-load-de-${var.environment}"
  description = "Fetch actual electricity load for Germany"

  group_name = aws_scheduler_schedule_group.this.name

  flexible_time_window {
    mode = "OFF"
  }

  # Keep cron to stay aligned (00:00, 06:00, 12:00, 18:00 UTC)
  schedule_expression          = "cron(0 */6 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = var.lambda_function_arn
    role_arn = aws_iam_role.scheduler_invoke_lambda.arn
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
}

############################################
# Schedule 3: Generation Forecast (AT)
# Daily at 06:00 UTC
############################################
resource "aws_scheduler_schedule" "generation_forecast_at" {
  name        = "${var.project}-generation-forecast-at-${var.environment}"
  description = "Fetch generation forecast for Austria"

  group_name = aws_scheduler_schedule_group.this.name

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 6 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = var.lambda_function_arn
    role_arn = aws_iam_role.scheduler_invoke_lambda.arn
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
}