# OpenSearch Outputs
output "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  value       = aws_opensearch_domain.main.endpoint
}

output "opensearch_dashboard_endpoint" {
  description = "OpenSearch Dashboards endpoint"
  value       = aws_opensearch_domain.main.dashboard_endpoint
}

output "opensearch_domain_id" {
  description = "OpenSearch domain ID"
  value       = aws_opensearch_domain.main.domain_id
}

output "opensearch_arn" {
  description = "OpenSearch domain ARN"
  value       = aws_opensearch_domain.main.arn
}

output "opensearch_master_username" {
  description = "OpenSearch master username"
  value       = var.opensearch_master_user_name
  sensitive   = true
}


# Environment Configuration Output
output "environment_config" {
  description = "Configuration values for .env file"
  value = {
    OPENSEARCH_HOST               = aws_opensearch_domain.main.endpoint
    OPENSEARCH_PORT               = "443"
    OPENSEARCH_USERNAME           = var.opensearch_master_user_name
    OPENSEARCH_INDEX              = "documents"
    OPENSEARCH_USE_SSL            = "true"
    AWS_REGION                    = var.aws_region
   }
  sensitive = true
}

# Summary Output
output "deployment_summary" {
  description = "Summary of deployed resources"
  value = {
    project_name         = var.project_name
    environment          = var.environment
    aws_region           = var.aws_region
    opensearch_domain    = aws_opensearch_domain.main.domain_name
    opensearch_version   = var.opensearch_version
    opensearch_instances = var.opensearch_instance_count
  }
}
