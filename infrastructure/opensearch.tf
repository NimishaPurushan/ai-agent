# OpenSearch Domain
resource "aws_opensearch_domain" "main" {
  domain_name    = "${var.project_name}-${var.environment}"
  engine_version = "OpenSearch_${var.opensearch_version}"

  cluster_config {
    instance_type  = var.opensearch_instance_type
    instance_count = var.opensearch_instance_count

    # Enable dedicated master nodes for production
    dedicated_master_enabled = var.opensearch_instance_count > 2
    dedicated_master_type    = var.opensearch_instance_count > 2 ? "t3.small.search" : null
    dedicated_master_count   = var.opensearch_instance_count > 2 ? 3 : null

    # Enable zone awareness for multi-AZ deployment
    zone_awareness_enabled = var.opensearch_instance_count > 1

    dynamic "zone_awareness_config" {
      for_each = var.opensearch_instance_count > 1 ? [1] : []
      content {
        availability_zone_count = 2
      }
    }
  }

  # EBS storage configuration
  ebs_options {
    ebs_enabled = true
    volume_size = var.opensearch_ebs_volume_size
    volume_type = "gp3"
    iops        = 3000
    throughput  = 125
  }

  # Encryption at rest
  encrypt_at_rest {
    enabled = true
  }

  # Node-to-node encryption
  node_to_node_encryption {
    enabled = true
  }

  # Domain endpoint options
  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"

    # Enable custom endpoint (optional)
    # custom_endpoint_enabled = true
    # custom_endpoint         = "search.yourdomain.com"
  }

  # Advanced security options (Fine-grained access control)
  advanced_security_options {
    enabled                        = true
    internal_user_database_enabled = true

    master_user_options {
      master_user_name     = var.opensearch_master_user_name
      master_user_password = var.opensearch_master_user_password
    }
  }

  # Advanced options
  advanced_options = {
    "rest.action.multi.allow_explicit_index" = "true"
    "override_main_response_version"         = "false"
  }

  # Access policy
  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "*"
        }
        Action   = "es:*"
        Resource = "arn:aws:es:${var.aws_region}:${data.aws_caller_identity.current.account_id}:domain/${var.project_name}-${var.environment}/*"
        Condition = {
          IpAddress = {
            "aws:SourceIp" = var.allowed_cidr_blocks
          }
        }
      },
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::676206928056:user/zell-fresh"
        }
        Action   = "es:*"
        Resource = "arn:aws:es:${var.aws_region}:${data.aws_caller_identity.current.account_id}:domain/${var.project_name}-${var.environment}/*"
      }
    ]
  })

  # Automated snapshots
  snapshot_options {
    automated_snapshot_start_hour = 23
  }

  # Log publishing options
  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_application_logs.arn
    log_type                 = "INDEX_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_search_logs.arn
    log_type                 = "SEARCH_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_error_logs.arn
    log_type                 = "ES_APPLICATION_LOGS"
  }

  tags = merge(
    {
      Name = "${var.project_name}-${var.environment}-opensearch"
    },
    var.additional_tags
  )

  depends_on = [
    aws_iam_service_linked_role.opensearch
  ]
}

# Service-linked role for OpenSearch
resource "aws_iam_service_linked_role" "opensearch" {
  aws_service_name = "es.amazonaws.com"
  description      = "Service-linked role for OpenSearch"

  # Only create if it doesn't exist
  lifecycle {
    ignore_changes = all
  }
}

# CloudWatch Log Groups for OpenSearch logs
resource "aws_cloudwatch_log_group" "opensearch_application_logs" {
  name              = "/aws/opensearch/${var.project_name}-${var.environment}/application-logs"
  retention_in_days = 7

  tags = merge(
    {
      Name = "${var.project_name}-${var.environment}-opensearch-app-logs"
    },
    var.additional_tags
  )
}

resource "aws_cloudwatch_log_group" "opensearch_search_logs" {
  name              = "/aws/opensearch/${var.project_name}-${var.environment}/search-logs"
  retention_in_days = 7

  tags = merge(
    {
      Name = "${var.project_name}-${var.environment}-opensearch-search-logs"
    },
    var.additional_tags
  )
}

resource "aws_cloudwatch_log_group" "opensearch_error_logs" {
  name              = "/aws/opensearch/${var.project_name}-${var.environment}/error-logs"
  retention_in_days = 14

  tags = merge(
    {
      Name = "${var.project_name}-${var.environment}-opensearch-error-logs"
    },
    var.additional_tags
  )
}

# CloudWatch Log Resource Policy for OpenSearch
resource "aws_cloudwatch_log_resource_policy" "opensearch" {
  policy_name = "${var.project_name}-${var.environment}-opensearch-logs"

  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "es.amazonaws.com"
        }
        Action = [
          "logs:PutLogEvents",
          "logs:CreateLogStream"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/opensearch/${var.project_name}-${var.environment}/*"
      }
    ]
  })
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
