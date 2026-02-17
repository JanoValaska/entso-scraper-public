variable "project" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment name (demo, dev, prod)"
}

variable "lambda_function_arn" {
  type        = string
  description = "ARN of the Lambda function to trigger"
}