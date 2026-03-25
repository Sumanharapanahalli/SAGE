# ================================================================
# CloudWatch Dashboards — SAGE Elder Fall Detection Monitoring
# Metrics: Alert Latency, GPS Accuracy, Device Connectivity,
#          Fall Event Throughput
# Resolution: 5-minute periods (period = 300) across all metrics
# ================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ── Variables ──────────────────────────────────────────────────
variable "environment" {
  description = "Deployment environment (staging, production)"
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be staging or production."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "ecs_cluster_name" {
  description = "ECS cluster name"
  type        = string
  default     = "sage-staging"
}

variable "ecs_service_name" {
  description = "ECS service name"
  type        = string
  default     = "sage-backend-staging"
}

variable "alert_latency_warning_ms" {
  description = "Alert latency P95 warning threshold (milliseconds)"
  type        = number
  default     = 500
}

variable "alert_latency_critical_ms" {
  description = "Alert latency P95 critical threshold (milliseconds)"
  type        = number
  default     = 1000
}

variable "gps_fix_rate_warning" {
  description = "GPS fix rate warning threshold (0.0–1.0)"
  type        = number
  default     = 0.95
}

variable "device_online_ratio_warning" {
  description = "Device online ratio warning threshold (0.0–1.0)"
  type        = number
  default     = 0.90
}

variable "sns_alert_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarm notifications"
  type        = string
}

# ── Locals ─────────────────────────────────────────────────────
locals {
  name_prefix = "sage-${var.environment}"
  namespace   = "SAGE/ElderFallDetection"
  period_5min = 300

  common_tags = {
    Environment = var.environment
    Project     = "SAGE"
    ManagedBy   = "Terraform"
    Component   = "Monitoring"
  }
}

# ================================================================
# MAIN DASHBOARD — SAGE Elder Fall Detection (all 4 core metrics)
# ================================================================
resource "aws_cloudwatch_dashboard" "sage_main" {
  dashboard_name = "${local.name_prefix}-fall-detection"

  dashboard_body = jsonencode({
    widgets = [
      # ── Header ────────────────────────────────────────────────
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "## SAGE Elder Fall Detection — ${upper(var.environment)} | 5-minute resolution | ${var.aws_region}"
        }
      },

      # ── METRIC 1: Alert Latency P50/P95/P99 ──────────────────
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 12
        height = 6
        properties = {
          title   = "Alert Latency — P50 / P95 / P99 (ms)"
          view    = "timeSeries"
          stacked = false
          period  = local.period_5min
          region  = var.aws_region
          yAxis = {
            left = { label = "Latency (ms)", showUnits = false, min = 0 }
          }
          annotations = {
            horizontal = [
              { label = "Warning (P95)",  value = var.alert_latency_warning_ms,  color = "#f89256" },
              { label = "Critical (P95)", value = var.alert_latency_critical_ms, color = "#d13212" }
            ]
          }
          metrics = [
            [local.namespace, "AlertLatencyMs", "Environment", var.environment,
              { stat = "p50", label = "P50", color = "#1f77b4", period = local.period_5min }],
            [local.namespace, "AlertLatencyMs", "Environment", var.environment,
              { stat = "p95", label = "P95", color = "#f89256", period = local.period_5min }],
            [local.namespace, "AlertLatencyMs", "Environment", var.environment,
              { stat = "p99", label = "P99", color = "#d13212", period = local.period_5min }]
          ]
        }
      },

      # Alert volume count
      {
        type   = "metric"
        x      = 12
        y      = 1
        width  = 12
        height = 6
        properties = {
          title   = "Alert Volume (events / 5 min)"
          view    = "timeSeries"
          stacked = false
          period  = local.period_5min
          region  = var.aws_region
          yAxis   = { left = { label = "Count", showUnits = false, min = 0 } }
          metrics = [
            [local.namespace, "AlertLatencyMs", "Environment", var.environment,
              { stat = "SampleCount", label = "Alert Events", color = "#2ca02c", period = local.period_5min }]
          ]
        }
      },

      # ── METRIC 2: GPS Fix Rate ────────────────────────────────
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 12
        height = 6
        properties = {
          title   = "GPS Fix Rate (ratio, 5-min avg)"
          view    = "timeSeries"
          stacked = false
          period  = local.period_5min
          region  = var.aws_region
          yAxis = {
            left = { label = "Fix Rate", showUnits = false, min = 0, max = 1 }
          }
          annotations = {
            horizontal = [
              {
                label = "Warning threshold"
                value = var.gps_fix_rate_warning
                color = "#f89256"
                fill  = "below"
              }
            ]
          }
          metrics = [
            [local.namespace, "GpsFixRate", "Environment", var.environment,
              { stat = "Average", label = "GPS Fix Rate (avg)", color = "#17becf", period = local.period_5min }],
            [local.namespace, "GpsFixRate", "Environment", var.environment,
              { stat = "Minimum", label = "GPS Fix Rate (min)", color = "#d62728", period = local.period_5min }]
          ]
        }
      },

      # GPS HDOP accuracy
      {
        type   = "metric"
        x      = 12
        y      = 7
        width  = 12
        height = 6
        properties = {
          title   = "GPS Accuracy — HDOP (lower is better)"
          view    = "timeSeries"
          stacked = false
          period  = local.period_5min
          region  = var.aws_region
          yAxis   = { left = { label = "HDOP", showUnits = false, min = 0 } }
          annotations = {
            horizontal = [
              { label = "Acceptable (HDOP ≤ 2)", value = 2, color = "#f89256" },
              { label = "Poor (HDOP > 5)",        value = 5, color = "#d13212" }
            ]
          }
          metrics = [
            [local.namespace, "GpsHdop", "Environment", var.environment,
              { stat = "Average", label = "HDOP Avg", color = "#9467bd", period = local.period_5min }],
            [local.namespace, "GpsHdop", "Environment", var.environment,
              { stat = "p95", label = "HDOP P95", color = "#d62728", period = local.period_5min }]
          ]
        }
      },

      # ── METRIC 3: Device Connectivity ────────────────────────
      {
        type   = "metric"
        x      = 0
        y      = 13
        width  = 12
        height = 6
        properties = {
          title   = "Device Online Ratio (5-min avg)"
          view    = "timeSeries"
          stacked = false
          period  = local.period_5min
          region  = var.aws_region
          yAxis = {
            left = { label = "Online Ratio", showUnits = false, min = 0, max = 1 }
          }
          annotations = {
            horizontal = [
              {
                label = "Warning threshold"
                value = var.device_online_ratio_warning
                color = "#f89256"
                fill  = "below"
              }
            ]
          }
          metrics = [
            [local.namespace, "DeviceOnlineRatio", "Environment", var.environment,
              { stat = "Average", label = "Online Ratio", color = "#2ca02c", period = local.period_5min }]
          ]
        }
      },

      # Device count breakdown
      {
        type   = "metric"
        x      = 12
        y      = 13
        width  = 12
        height = 6
        properties = {
          title   = "Device Count — Online / Offline / Total"
          view    = "timeSeries"
          stacked = false
          period  = local.period_5min
          region  = var.aws_region
          yAxis   = { left = { label = "Devices", showUnits = false, min = 0 } }
          metrics = [
            [local.namespace, "DeviceTotalCount", "Environment", var.environment,
              { stat = "Maximum", label = "Total",   color = "#7f7f7f", period = local.period_5min }],
            [local.namespace, "DeviceOnlineCount", "Environment", var.environment,
              { stat = "Average", label = "Online",  color = "#2ca02c", period = local.period_5min }],
            [local.namespace, "DeviceOfflineCount", "Environment", var.environment,
              { stat = "Average", label = "Offline", color = "#d62728", period = local.period_5min }]
          ]
        }
      },

      # ── METRIC 4: Fall Event Throughput ──────────────────────
      {
        type   = "metric"
        x      = 0
        y      = 19
        width  = 12
        height = 6
        properties = {
          title   = "Fall Event Throughput (events / 5 min)"
          view    = "timeSeries"
          stacked = false
          period  = local.period_5min
          region  = var.aws_region
          yAxis   = { left = { label = "Events", showUnits = false, min = 0 } }
          metrics = [
            [local.namespace, "FallEventCount", "Environment", var.environment, "EventType", "confirmed",
              { stat = "Sum", label = "Confirmed Falls", color = "#d62728", period = local.period_5min }],
            [local.namespace, "FallEventCount", "Environment", var.environment, "EventType", "false_positive",
              { stat = "Sum", label = "False Positives", color = "#f89256", period = local.period_5min }],
            [local.namespace, "FallEventCount", "Environment", var.environment, "EventType", "all",
              { stat = "Sum", label = "Total Events", color = "#7f7f7f", period = local.period_5min }]
          ]
        }
      },

      # Fall event end-to-end latency
      {
        type   = "metric"
        x      = 12
        y      = 19
        width  = 12
        height = 6
        properties = {
          title   = "Fall E2E Latency — Detection → Alert Sent (ms)"
          view    = "timeSeries"
          stacked = false
          period  = local.period_5min
          region  = var.aws_region
          yAxis   = { left = { label = "Latency (ms)", showUnits = false, min = 0 } }
          metrics = [
            [local.namespace, "FallEventE2ELatencyMs", "Environment", var.environment,
              { stat = "p50", label = "P50", color = "#1f77b4", period = local.period_5min }],
            [local.namespace, "FallEventE2ELatencyMs", "Environment", var.environment,
              { stat = "p95", label = "P95", color = "#f89256", period = local.period_5min }],
            [local.namespace, "FallEventE2ELatencyMs", "Environment", var.environment,
              { stat = "p99", label = "P99", color = "#d13212", period = local.period_5min }]
          ]
        }
      },

      # ── ECS Service Health ────────────────────────────────────
      {
        type   = "metric"
        x      = 0
        y      = 25
        width  = 24
        height = 5
        properties = {
          title   = "ECS Service Health — ${var.ecs_cluster_name}/${var.ecs_service_name}"
          view    = "timeSeries"
          stacked = false
          period  = local.period_5min
          region  = var.aws_region
          metrics = [
            ["ECS/ContainerInsights", "RunningTaskCount",
              "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name,
              { stat = "Average", label = "Running Tasks", color = "#2ca02c", period = local.period_5min }],
            ["ECS/ContainerInsights", "DesiredTaskCount",
              "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name,
              { stat = "Average", label = "Desired Tasks", color = "#7f7f7f", period = local.period_5min }],
            ["ECS/ContainerInsights", "CPUUtilization",
              "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name,
              { stat = "Average", label = "CPU %", yAxis = "right", color = "#ff7f0e", period = local.period_5min }],
            ["ECS/ContainerInsights", "MemoryUtilization",
              "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name,
              { stat = "Average", label = "Memory %", yAxis = "right", color = "#9467bd", period = local.period_5min }]
          ]
        }
      }
    ]
  })

  tags = local.common_tags
}

# ================================================================
# CLOUDWATCH ALARMS
# ================================================================

resource "aws_cloudwatch_metric_alarm" "alert_latency_p95_warning" {
  alarm_name          = "${local.name_prefix}-alert-latency-p95-warning"
  alarm_description   = "Alert latency P95 exceeded ${var.alert_latency_warning_ms}ms for 10 minutes"
  namespace           = local.namespace
  metric_name         = "AlertLatencyMs"
  statistic           = "p95"
  period              = local.period_5min
  evaluation_periods  = 2
  threshold           = var.alert_latency_warning_ms
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = { Environment = var.environment }

  alarm_actions = [var.sns_alert_topic_arn]
  ok_actions    = [var.sns_alert_topic_arn]
  tags          = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alert_latency_p95_critical" {
  alarm_name          = "${local.name_prefix}-alert-latency-p95-critical"
  alarm_description   = "CRITICAL: Alert latency P95 exceeded ${var.alert_latency_critical_ms}ms"
  namespace           = local.namespace
  metric_name         = "AlertLatencyMs"
  statistic           = "p95"
  period              = local.period_5min
  evaluation_periods  = 1
  threshold           = var.alert_latency_critical_ms
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = { Environment = var.environment }

  alarm_actions = [var.sns_alert_topic_arn]
  ok_actions    = [var.sns_alert_topic_arn]
  tags          = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "gps_fix_rate_warning" {
  alarm_name          = "${local.name_prefix}-gps-fix-rate-warning"
  alarm_description   = "GPS fix rate dropped below ${var.gps_fix_rate_warning} for 10 minutes"
  namespace           = local.namespace
  metric_name         = "GpsFixRate"
  statistic           = "Average"
  period              = local.period_5min
  evaluation_periods  = 2
  threshold           = var.gps_fix_rate_warning
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"

  dimensions = { Environment = var.environment }

  alarm_actions = [var.sns_alert_topic_arn]
  ok_actions    = [var.sns_alert_topic_arn]
  tags          = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "device_online_ratio_warning" {
  alarm_name          = "${local.name_prefix}-device-online-ratio-warning"
  alarm_description   = "Device online ratio dropped below ${var.device_online_ratio_warning}"
  namespace           = local.namespace
  metric_name         = "DeviceOnlineRatio"
  statistic           = "Average"
  period              = local.period_5min
  evaluation_periods  = 2
  threshold           = var.device_online_ratio_warning
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"

  dimensions = { Environment = var.environment }

  alarm_actions = [var.sns_alert_topic_arn]
  ok_actions    = [var.sns_alert_topic_arn]
  tags          = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "fall_event_pipeline_stalled" {
  alarm_name          = "${local.name_prefix}-fall-event-pipeline-stalled"
  alarm_description   = "No fall events processed in 30 minutes — pipeline may be stalled"
  namespace           = local.namespace
  metric_name         = "FallEventCount"
  statistic           = "Sum"
  period              = local.period_5min
  evaluation_periods  = 6
  threshold           = 0
  comparison_operator = "LessThanOrEqualToThreshold"
  treat_missing_data  = "breaching"

  dimensions = {
    Environment = var.environment
    EventType   = "all"
  }

  alarm_actions = [var.sns_alert_topic_arn]
  ok_actions    = [var.sns_alert_topic_arn]
  tags          = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "ecs_running_tasks_low" {
  alarm_name          = "${local.name_prefix}-ecs-running-tasks-low"
  alarm_description   = "ECS running task count below desired (service degraded)"
  namespace           = "ECS/ContainerInsights"
  metric_name         = "RunningTaskCount"
  statistic           = "Average"
  period              = local.period_5min
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.ecs_service_name
  }

  alarm_actions = [var.sns_alert_topic_arn]
  ok_actions    = [var.sns_alert_topic_arn]
  tags          = local.common_tags
}

# ── Composite alarm — overall system health ──────────────────
resource "aws_cloudwatch_composite_alarm" "system_health" {
  alarm_name        = "${local.name_prefix}-system-health"
  alarm_description = "Overall SAGE Elder Fall Detection system health — fires when any critical alarm is active"

  alarm_rule = join(" OR ", [
    "ALARM(${aws_cloudwatch_metric_alarm.alert_latency_p95_critical.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.gps_fix_rate_warning.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.device_online_ratio_warning.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.fall_event_pipeline_stalled.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.ecs_running_tasks_low.alarm_name})"
  ])

  alarm_actions = [var.sns_alert_topic_arn]
  ok_actions    = [var.sns_alert_topic_arn]
  tags          = local.common_tags
}

# ================================================================
# LOG METRIC FILTERS — extract custom metrics from ECS log JSON
# ================================================================

resource "aws_cloudwatch_log_metric_filter" "fall_event_count" {
  name           = "${local.name_prefix}-fall-event-count"
  pattern        = "{ $.event_type = \"fall_detected\" }"
  log_group_name = "/ecs/${var.ecs_service_name}"

  metric_transformation {
    name          = "FallEventCount"
    namespace     = local.namespace
    value         = "1"
    unit          = "Count"
    default_value = "0"
    dimensions = {
      Environment = var.environment
      EventType   = "$.classification"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "alert_latency" {
  name           = "${local.name_prefix}-alert-latency"
  pattern        = "{ $.metric = \"alert_latency_ms\" }"
  log_group_name = "/ecs/${var.ecs_service_name}"

  metric_transformation {
    name      = "AlertLatencyMs"
    namespace = local.namespace
    value     = "$.value"
    unit      = "Milliseconds"
    dimensions = {
      Environment = var.environment
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "gps_fix_rate" {
  name           = "${local.name_prefix}-gps-fix-rate"
  pattern        = "{ $.metric = \"gps_fix_rate\" }"
  log_group_name = "/ecs/${var.ecs_service_name}"

  metric_transformation {
    name      = "GpsFixRate"
    namespace = local.namespace
    value     = "$.value"
    unit      = "None"
    dimensions = {
      Environment = var.environment
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "device_online_ratio" {
  name           = "${local.name_prefix}-device-online-ratio"
  pattern        = "{ $.metric = \"device_online_ratio\" }"
  log_group_name = "/ecs/${var.ecs_service_name}"

  metric_transformation {
    name      = "DeviceOnlineRatio"
    namespace = local.namespace
    value     = "$.value"
    unit      = "None"
    dimensions = {
      Environment = var.environment
    }
  }
}

# ================================================================
# OUTPUTS
# ================================================================

output "dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.sage_main.dashboard_name}"
}

output "composite_alarm_arn" {
  description = "Composite system health alarm ARN"
  value       = aws_cloudwatch_composite_alarm.system_health.arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = aws_cloudwatch_dashboard.sage_main.dashboard_name
}
