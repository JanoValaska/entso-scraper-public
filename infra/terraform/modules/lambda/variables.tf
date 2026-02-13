variable "vpc_id" {
  type        = string
  description = "ID of the VPC where Lambda will be deployed"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "IDs of the private subnets for Lambda VPC configuration"
}

variable "data_bucket_arn" {
  type        = string
  description = "ARN of the S3 bucket where data will be stored"
}

variable "data_bucket_id" {
  type        = string
  description = "ID/Name of the S3 bucket where data will be stored"
}

variable "project" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment name (demo, dev, prod)"
}

variable "handler" {
  type        = string
  description = "Lambda function handler"
  default     = "lambda_function.handler"
}

variable "runtime" {
  type        = string
  description = "Lambda function runtime"
  default     = "python3.13"
}

variable "memory_size" {
  type        = number
  description = "Lambda function memory size"
  default     = 512
}

variable "timeout" {
  type        = number
  description = "Lambda function timeout in seconds"
  default     = 300
}

variable "environment_variables" {
  type        = map(string)
  description = "Additional environment variables for the Lambda function"
  default     = {}
}

variable "source_path" {
  type        = string
  description = "Path to the Lambda source code"
  default     = "src"
}
