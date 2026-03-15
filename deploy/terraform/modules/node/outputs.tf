output "node_ip" {
  description = "Public IP of the RustChain node"
  value = var.cloud_provider == "digitalocean" ? (
    length(digitalocean_droplet.node) > 0 ? digitalocean_droplet.node[0].ipv4_address : ""
  ) : (
    length(aws_instance.node) > 0 ? aws_instance.node[0].public_ip : ""
  )
}

output "node_id" {
  description = "Provider-specific node ID"
  value = var.cloud_provider == "digitalocean" ? (
    length(digitalocean_droplet.node) > 0 ? tostring(digitalocean_droplet.node[0].id) : ""
  ) : (
    length(aws_instance.node) > 0 ? aws_instance.node[0].id : ""
  )
}

output "node_name" {
  value = local.node_name
}
