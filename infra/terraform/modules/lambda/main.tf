# IAM Role for Lambda
resource "aws_iam_role" "lambda_exec" {
  name = "${var.project}-lambda-exec-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Sid    = ""
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Attach basic Lambda execution policy (CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Attach VPC access policy
resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Custom policy for S3 access
resource "aws_iam_role_policy" "lambda_s3" {
  name = "${var.project}-lambda-s3-${var.environment}"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Effect = "Allow"
        Resource = [
          var.data_bucket_arn,
          "${var.data_bucket_arn}/*"
        ]
      }
    ]
  })
}

# Custom policy for SSM Parameter Store access
resource "aws_iam_role_policy" "lambda_ssm" {
  name = "${var.project}-lambda-ssm-${var.environment}"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:ssm:*:*:parameter/${var.project}/${var.environment}/*"
      },
      {
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# Security Group for Lambda
resource "aws_security_group" "lambda" {
  name        = "${var.project}-lambda-sg-${var.environment}"
  description = "Security group for ENTSO-E Scraper Lambda"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project}-lambda-sg-${var.environment}"
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Zip the Lambda source code (code-only)
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.root}/../../../../${var.source_path}"
  output_path = "${path.module}/lambda_function.zip"
}

################################################################################
# Dependencies Layer
# Expects deps-layer.zip to be built outside Terraform (CI/local) at:
#   infra/terraform/modules/lambda/deps-layer.zip
################################################################################

resource "aws_lambda_layer_version" "deps" {
  layer_name          = "${var.project}-deps-${var.environment}"
  filename            = "${path.module}/deps-layer.zip"
  source_code_hash    = filebase64sha256("${path.module}/deps-layer.zip")
  compatible_runtimes = [var.runtime]

  description = "Python deps layer (pandas, entsoe-py) for ${var.runtime}"
}

# Lambda Function
resource "aws_lambda_function" "this" {
  function_name = "${var.project}-lambda-${var.environment}"
  role          = aws_iam_role.lambda_exec.arn
  handler       = var.handler

  runtime = var.runtime

  memory_size = var.memory_size
  timeout     = var.timeout

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  layers = [aws_lambda_layer_version.deps.arn]

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = merge(
      {
        DATA_BUCKET_NAME = var.data_bucket_id
      },
      var.environment_variables
    )
  }

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# CloudWatch Log Group for the Lambda
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${aws_lambda_function.this.function_name}"
  retention_in_days = 14

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Note: EventBridge scheduling is now handled by a separate eventbridge module
