
variable "aws_region" {
  description = "AWS region for the serverless platform"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Short project identifier"
  type        = string
  default     = "csv-analytics"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "lambda_memory_mb" {
  description = "Lambda memory in MB"
  type        = number
  default     = 512

  validation {
    condition     = var.lambda_memory_mb >= 128 && var.lambda_memory_mb <= 10240
    error_message = "Lambda memory must be between 128 and 10240 MB."
  }
}

variable "lambda_timeout_seconds" {
  description = "Maximum Lambda execution duration"
  type        = number
  default     = 60

  validation {
    condition     = var.lambda_timeout_seconds >= 3 && var.lambda_timeout_seconds <= 900
    error_message = "Lambda timeout must be between 3 and 900 seconds."
  }
}

variable "max_file_size_bytes" {
  description = "Maximum accepted CSV file size"
  type        = number
  default     = 10485760
}

variable "log_retention_days" {
  description = "CloudWatch log retention"
  type        = number
  default     = 7
}

