variable "aws_region" {
  description = "AWS region where resources will be created"
  type        = string
  default     = "us-east-1" # CloudFront works best with us-east-1
}

variable "bucket_name" {
  description = "Name of the S3 bucket (must be globally unique)"
  type        = string
  default     = "sportsvisio-api-docs"
}

variable "environment" {
  description = "Environment name for tagging"
  type        = string
  default     = "production"
}

variable "domain_name" {
  description = "Custom domain name for CloudFront distribution (e.g., docs.sportsvisio-api.com)"
  type        = string
  default     = "docs.sportsvisio-api.com"
}

variable "create_acm_certificate" {
  description = "Whether to create a new ACM certificate (true) or use an existing one (false)"
  type        = bool
  default     = false
}

variable "acm_certificate_arn" {
  description = "ARN of existing ACM certificate (required if create_acm_certificate = false)"
  type        = string
  default     = ""
}
