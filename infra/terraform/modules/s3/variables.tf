variable "bucket_name" {
  type        = string
  description = "Name of the S3 bucket"
}

variable "force_destroy" {
  type        = bool
  description = "Whether to force destroy the bucket"
  default     = false
}

variable "versioning" {
  type        = bool
  description = "Whether to enable versioning"
  default     = false
}

variable "environment" {
  type        = string
  description = "Environment name (demo, dev, prod). Leave null for bootstrap/shared resources."
  default     = null
}

variable "project" {
  type        = string
  description = "Project name"
}
