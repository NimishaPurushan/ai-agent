variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "ai-bot-rag"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# OpenSearch Configuration
variable "opensearch_domain_name" {
  description = "OpenSearch domain name"
  type        = string
  default     = "ai-bot-search"
}

variable "opensearch_version" {
  description = "OpenSearch version"
  type        = string
  default     = "2.11"
}

variable "opensearch_instance_type" {
  description = "Instance type for OpenSearch nodes"
  type        = string
  default     = "t3.small.search" # Free tier eligible: t3.small.search or t2.small.search
}

variable "opensearch_instance_count" {
  description = "Number of instances in the OpenSearch domain"
  type        = number
  default     = 1
}

variable "opensearch_ebs_volume_size" {
  description = "EBS volume size for OpenSearch (GB)"
  type        = number
  default     = 10
}

variable "opensearch_master_user_name" {
  description = "Master username for OpenSearch"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "opensearch_master_user_password" {
  description = "Master password for OpenSearch (min 8 chars, must include uppercase, lowercase, number, special char)"
  type        = string
  sensitive   = true
  # Password will be provided via terraform.tfvars or environment variable
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "enable_vpc" {
  description = "Whether to create VPC resources (set false for public OpenSearch access)"
  type        = bool
  default     = false # Set to true for production with VPC
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access OpenSearch"
  type        = list(string)
  default     = ["0.0.0.0/0"] # WARNING: Open to all. Restrict in production!
}

# Tags
variable "additional_tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}
