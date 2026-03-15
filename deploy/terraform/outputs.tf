# ──────────────────────────────────────────────────────────────
# RustChain Infrastructure — Outputs
# ──────────────────────────────────────────────────────────────

output "node_ips" {
  description = "Public IP addresses of RustChain nodes"
  value       = module.node[*].node_ip
}

output "dashboard_urls" {
  description = "RustChain dashboard URLs"
  value = [
    for ip in module.node[*].node_ip :
    var.domain_name != "" ? "https://${var.domain_name}" : "http://${ip}"
  ]
}

output "ssh_commands" {
  description = "SSH commands to connect to each node"
  value = [
    for ip in module.node[*].node_ip :
    "ssh root@${ip}"
  ]
}

output "grafana_url" {
  description = "Grafana dashboard URL (if monitoring enabled)"
  value = var.enable_monitoring && length(module.node) > 0 ? (
    var.domain_name != "" ? "https://${var.domain_name}:3000" : "http://${module.node[0].node_ip}:3000"
  ) : "monitoring disabled"
}

output "prometheus_url" {
  description = "Prometheus URL (if monitoring enabled)"
  value = var.enable_monitoring && length(module.node) > 0 ? (
    "http://${module.node[0].node_ip}:9090"
  ) : "monitoring disabled"
}

output "api_endpoints" {
  description = "RustChain API endpoints"
  value = [
    for ip in module.node[*].node_ip :
    "http://${ip}:8099"
  ]
}
