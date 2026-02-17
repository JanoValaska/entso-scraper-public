output "lambda_function_name" {
  value       = aws_lambda_function.this.function_name
  description = "Name of the Lambda function"
}

output "lambda_function_arn" {
  value       = aws_lambda_function.this.arn
  description = "ARN of the Lambda function"
}

output "lambda_role_arn" {
  value       = aws_iam_role.lambda_exec.arn
  description = "ARN of the Lambda IAM role"
}
