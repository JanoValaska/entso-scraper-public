variable "vpc_id" {
  type        = string
  description = "ID of the VPC"
}

variable "public_subnet_id" {
  type        = string
  description = "ID of the public subnet where NAT instance will reside"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "IDs of the private subnets to route through NAT"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type for fck-nat"
  default     = "t4g.nano"
}

variable "project" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment name (demo, dev, prod)"
}
