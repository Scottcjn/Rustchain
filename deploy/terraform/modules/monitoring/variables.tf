variable "node_ips" {
  description = "List of RustChain node IPs to scrape"
  type        = list(string)
}

variable "grafana_admin_password" {
  type      = string
  sensitive = true
}
