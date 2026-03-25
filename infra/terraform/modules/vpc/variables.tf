variable "name_prefix" {
  type = string
}
variable "cidr" {
  type    = string
  default = "10.0.0.0/16"
}
variable "availability_zones" {
  type = list(string)
}
variable "aws_region" {
  type = string
}
variable "kms_key_arn" {
  type    = string
  default = ""
}
