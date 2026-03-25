variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev / staging / prod)"
  type        = string
  default     = "prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project_name" {
  description = "Project name — used as prefix for all resource names"
  type        = string
  default     = "fall-detection"
}

# ── VPC ──────────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.10.0.0/16"
}

variable "availability_zones" {
  description = "List of AZs for subnet placement (minimum 2 for HA)"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (one per AZ)"
  type        = list(string)
  default     = ["10.10.1.0/24", "10.10.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (one per AZ)"
  type        = list(string)
  default     = ["10.10.11.0/24", "10.10.12.0/24"]
}

# ── MQTT (Amazon MQ) ─────────────────────────────────────────────────────────

variable "mqtt_broker_instance_type" {
  description = "Amazon MQ broker instance type"
  type        = string
  default     = "mq.m5.large"
}

variable "mqtt_username" {
  description = "MQTT broker admin username (password auto-generated)"
  type        = string
  default     = "ble_gateway"
  sensitive   = true
}

variable "mqtt_allowed_cidr_blocks" {
  description = "CIDR blocks allowed to connect to MQTT port 8883"
  type        = list(string)
  default     = ["10.10.0.0/16"] # restrict to VPC by default
}

# ── TimescaleDB (RDS PostgreSQL) ──────────────────────────────────────────────

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage_gb" {
  description = "Initial allocated storage in GiB"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage_gb" {
  description = "Upper storage autoscaling limit in GiB"
  type        = number
  default     = 500
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "fall_detection"
}

variable "db_username" {
  description = "PostgreSQL master username (password auto-generated)"
  type        = string
  default     = "sage_admin"
  sensitive   = true
}

variable "db_backup_retention_days" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 7
}

variable "db_multi_az" {
  description = "Enable Multi-AZ deployment for RDS"
  type        = bool
  default     = true
}

variable "db_init_runner_cidr" {
  description = "CIDR block of the machine that runs `terraform apply` (used for DB init access). Set to your VPN/bastion CIDR."
  type        = string
  default     = ""  # empty = skip null_resource DB init (run manually)
}

# ── Redis (ElastiCache) ───────────────────────────────────────────────────────

variable "redis_node_type" {
  description = "ElastiCache Redis node type — r7g family for <5ms p99"
  type        = string
  default     = "cache.r7g.large"
}

variable "redis_num_replicas" {
  description = "Number of read replicas per shard (0 = single node, no HA)"
  type        = number
  default     = 1
}

variable "redis_allowed_cidr_blocks" {
  description = "CIDR blocks allowed to connect to Redis port 6379"
  type        = list(string)
  default     = ["10.10.0.0/16"]
}

# ── Tagging ───────────────────────────────────────────────────────────────────

variable "extra_tags" {
  description = "Additional tags merged onto every resource"
  type        = map(string)
  default     = {}
}
