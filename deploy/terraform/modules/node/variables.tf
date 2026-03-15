variable "cloud_provider" {
  type = string
}

variable "do_region" {
  type    = string
  default = "nyc3"
}

variable "do_droplet_size" {
  type    = string
  default = "s-2vcpu-4gb"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "aws_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "aws_key_pair_name" {
  type    = string
  default = ""
}

variable "ssh_public_key" {
  type = string
}

variable "node_index" {
  description = "Index of this node (for naming)"
  type        = number
}

variable "cloud_init_script" {
  description = "Rendered cloud-init bootstrap script"
  type        = string
}

variable "environment" {
  type    = string
  default = "prod"
}
