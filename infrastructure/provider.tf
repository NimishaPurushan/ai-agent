terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Optional: Configure S3 backend for state management
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "ai-bot/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-state-lock"
  # }
}

provider "aws" {
  region = var.aws_region

  # Optional: Use specific profile
  # profile = var.aws_profile

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Application = "AI-Bot-RAG"
    }
  }
}
