
output "bucket_name" {
  description = "S3 bucket for uploaded files and reports"
  value       = aws_s3_bucket.files.bucket
}

output "queue_url" {
  description = "SQS processing queue URL"
  value       = aws_sqs_queue.processing.url
}

output "dlq_url" {
  description = "SQS dead-letter queue URL"
  value       = aws_sqs_queue.dlq.url
}

output "lambda_function_name" {
  description = "Lambda processor function name"
  value       = aws_lambda_function.processor.function_name
}

output "aws_region" {
  description = "Deployment region"
  value       = var.aws_region
}
