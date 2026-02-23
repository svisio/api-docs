# SportsVisio API Docs - Terraform Infrastructure

This Terraform configuration deploys the SportsVisio API documentation HTML file to AWS S3 and serves it via CloudFront CDN.

## Architecture

- **S3 Bucket**: Stores the static HTML file with public read access
- **CloudFront Distribution**: CDN for fast global content delivery with HTTPS
- **Cost**: Free Tier eligible (no charges with normal usage)

## Cost Optimization

This infrastructure is designed to be as cost-effective as possible:

- ✅ **S3**: First 5GB storage and 20,000 GET requests per month are free (Free Tier)
- ✅ **CloudFront**: First 1TB data transfer out and 10,000,000 requests per month are free for 12 months (Free Tier)
- ✅ **Price Class 100**: Uses only North America and Europe edge locations (cheapest option)
- ✅ **ACM SSL Certificate**: Free for CloudFront distributions
- ✅ **SNI SSL**: Uses Server Name Indication (free, vs dedicated IP at $600/month)
- ⚠️ **Route53**: If you use Route53 for DNS, hosted zones cost $0.50/month (can use external DNS to avoid this)

## Prerequisites

1. **AWS Account**: You need an active AWS account
2. **AWS CLI**: Install and configure with your credentials
   ```bash
   aws configure
   ```
3. **Terraform**: Install Terraform >= 1.0
   ```bash
   # macOS
   brew install terraform

   # Or download from: https://www.terraform.io/downloads
   ```

## Configuration

### Basic Configuration

Before deploying, you may want to customize the bucket name in [variables.tf](variables.tf):

```hcl
variable "bucket_name" {
  default = "sportsvisio-api-docs"  # Change this to a unique name
}
```

**Important**: S3 bucket names must be globally unique across all AWS accounts. If the default name is taken, you'll need to change it.

### Custom Domain & SSL Configuration

The configuration supports using a custom domain with SSL certificate. You have two options:

#### Option 1: Use an Existing ACM Certificate (Recommended)

If you already have an SSL certificate in AWS Certificate Manager for `docs.sportsvisio-api.com`:

1. Get your certificate ARN from ACM (must be in `us-east-1` region)
2. Set the variables:

```hcl
# In variables.tf or via command line
variable "domain_name" {
  default = "docs.sportsvisio-api.com"
}

variable "create_acm_certificate" {
  default = false
}

variable "acm_certificate_arn" {
  default = "arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id"
}
```

Or via command line:
```bash
terraform apply \
  -var="acm_certificate_arn=arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id"
```

#### Option 2: Create a New ACM Certificate

If you need Terraform to create a new certificate:

1. Set the variables:
```hcl
variable "create_acm_certificate" {
  default = true
}
```

2. After running `terraform apply`, you'll need to add DNS validation records to your domain. Terraform will output the required DNS records:
```bash
terraform output acm_certificate_validation_records
```

3. Add the CNAME records to your DNS provider (e.g., Route53, Cloudflare, etc.)

4. Wait for validation to complete (usually 5-30 minutes)

### DNS Configuration

After deployment, you need to point your domain to CloudFront:

1. Get your CloudFront distribution domain:
```bash
terraform output cloudfront_domain_name
# Example output: dr37cokakw408.cloudfront.net
```

2. Add a CNAME record in your DNS:
```
Type: CNAME
Name: docs.sportsvisio-api.com
Value: dr37cokakw408.cloudfront.net
```

**Note**: The CNAME value should be the CloudFront domain, not the full URL.

## Deployment

### 1. Initialize Terraform

```bash
cd terraform
terraform init
```

### 2. Review the Plan

```bash
terraform plan
```

This shows you what resources will be created.

### 3. Apply the Configuration

```bash
terraform apply
```

Type `yes` when prompted to confirm.

### 4. Get Your Website URL

After deployment completes, Terraform will output the CloudFront URL:

```bash
terraform output cloudfront_url
```

Example output: `https://d1234abcd5678.cloudfront.net`

## Accessing Your Site

Visit the CloudFront URL from the output above. Your API documentation will be available via HTTPS globally with CloudFront's CDN.

## Updating the HTML File

If you update [index.html](../docs/index.html), simply run:

```bash
terraform apply
```

Terraform will detect the change and upload the new version. Note that CloudFront caching may delay the update (up to 1 hour by default).

To force an immediate update, invalidate the CloudFront cache:

```bash
aws cloudfront create-invalidation \
  --distribution-id $(terraform output -raw cloudfront_distribution_id) \
  --paths "/*"
```

## Managing Costs

To avoid any unexpected charges:

1. **Monitor Free Tier Usage**: Check the AWS Billing Dashboard
2. **Set Up Billing Alerts**: Create a CloudWatch alarm for unexpected charges
3. **Destroy When Done**: If you're just testing, destroy the resources when done

## Destroy Resources

To remove all resources and stop any potential charges:

```bash
terraform destroy
```

Type `yes` when prompted to confirm.

## Outputs

After deployment, you'll have access to these outputs:

- `custom_domain_url` - Your custom domain URL (https://docs.sportsvisio-api.com)
- `cloudfront_url` - CloudFront distribution URL
- `cloudfront_domain_name` - CloudFront distribution domain (for CNAME record)
- `cloudfront_distribution_id` - Distribution ID for cache invalidation
- `acm_certificate_arn` - ARN of the SSL certificate
- `acm_certificate_validation_records` - DNS records needed for certificate validation (if creating new cert)
- `s3_bucket_name` - Name of the S3 bucket
- `s3_bucket_website_endpoint` - Direct S3 website endpoint (HTTP only)

## Security Notes

- The S3 bucket is configured with public read access (required for static website hosting)
- CloudFront enforces HTTPS by default (HTTP requests are redirected to HTTPS)
- No authentication is required to access the documentation (public API docs)

## Troubleshooting

### Bucket Name Already Exists

If you get an error about the bucket name already existing, change the `bucket_name` variable:

```bash
terraform apply -var="bucket_name=your-unique-bucket-name"
```

### CloudFront Not Showing Updates

CloudFront caches content for up to 24 hours. Either wait or run a cache invalidation:

```bash
aws cloudfront create-invalidation \
  --distribution-id $(terraform output -raw cloudfront_distribution_id) \
  --paths "/*"
```

### AWS Credentials Not Found

Make sure you've configured AWS CLI:

```bash
aws configure
```

Enter your AWS Access Key ID, Secret Access Key, and default region (use `us-east-1` for best CloudFront performance).

## Additional Resources

- [AWS S3 Static Website Hosting](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html)
- [AWS CloudFront Documentation](https://docs.aws.amazon.com/cloudfront/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
