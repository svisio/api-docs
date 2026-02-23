output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.website.id
}

output "s3_bucket_website_endpoint" {
  description = "S3 bucket website endpoint"
  value       = aws_s3_bucket_website_configuration.website.website_endpoint
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.website.id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name (use this URL to access your site)"
  value       = aws_cloudfront_distribution.website.domain_name
}

output "cloudfront_url" {
  description = "Full CloudFront URL for the website"
  value       = "https://${aws_cloudfront_distribution.website.domain_name}"
}

output "custom_domain_url" {
  description = "Custom domain URL for the website"
  value       = "https://${var.domain_name}"
}

output "acm_certificate_arn" {
  description = "ARN of the ACM certificate"
  value       = var.create_acm_certificate ? aws_acm_certificate.website[0].arn : var.acm_certificate_arn
}

output "acm_certificate_validation_records" {
  description = "DNS validation records for ACM certificate (if created)"
  value = var.create_acm_certificate ? [
    for dvo in aws_acm_certificate.website[0].domain_validation_options : {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      value  = dvo.resource_record_value
    }
  ] : []
}
