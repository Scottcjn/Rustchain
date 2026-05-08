//! Node transport layer with HTTPS direct or HTTP proxy fallback

use reqwest::{Client, Response};
use serde::Serialize;
use std::time::Duration;

/// Handles communication with the RustChain node
/// Tries HTTPS directly first, falls back to HTTP proxy if TLS fails
pub struct NodeTransport {
    client: Client,
    node_url: String,
    proxy_url: Option<String>,
    use_proxy: bool,
}

impl NodeTransport {
    /// Create a new transport with the given configuration.
    ///
    /// By default, TLS certificate validation is **enabled**.
    /// To disable validation (e.g. for local development against a test server
    /// with self-signed certificates), set the environment variable
    /// `RUSTCHAIN_DEV_INSECURE_TLS=1`. This is **strongly discouraged** in
    /// production — it exposes the miner to man-in-the-middle attacks.
    pub fn new(
        node_url: String,
        proxy_url: Option<String>,
        timeout: Duration,
    ) -> crate::Result<Self> {
        let insecure = std::env::var("RUSTCHAIN_DEV_INSECURE_TLS")
            .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
            .unwrap_or(false);

        let builder = Client::builder().timeout(timeout);
        let builder = if insecure {
            eprintln!(
                "WARNING: TLS certificate validation is DISABLED. \
                 This is INSECURE and exposes the miner to man-in-the-middle attacks. \
                 Do NOT use in production. Set via RUSTCHAIN_DEV_INSECURE_TLS=1."
            );
            builder.danger_accept_invalid_certs(true)
        } else {
            builder
        };

        let transport = Self {
            client: builder.build()?,
            node_url: node_url.trim_end_matches('/').to_string(),
            proxy_url: proxy_url.map(|u| u.trim_end_matches('/').to_string()),
            use_proxy: false,
        };

        Ok(transport)
    }

    /// Get the base URL to use (node or proxy)
    fn base_url(&self) -> &str {
        if self.use_proxy {
            self.proxy_url.as_ref().unwrap()
        } else {
            &self.node_url
        }
    }

    /// GET request to the node
    pub async fn get(&self, path: &str) -> crate::Result<Response> {
        let url = format!("{}{}", self.base_url(), path);
        let response = self.client.get(&url).send().await?;
        Ok(response)
    }

    /// GET request with query parameters
    pub async fn get_with_params<T: Serialize + ?Sized>(
        &self,
        path: &str,
        params: &T,
    ) -> crate::Result<Response> {
        let url = format!("{}{}", self.base_url(), path);
        let response = self.client.get(&url).query(params).send().await?;
        Ok(response)
    }

    /// POST request with JSON body
    pub async fn post_json<T: Serialize + ?Sized>(
        &self,
        path: &str,
        body: &T,
    ) -> crate::Result<Response> {
        let url = format!("{}{}", self.base_url(), path);
        let response = self.client.post(&url).json(body).send().await?;
        Ok(response)
    }

    /// Check if proxy is being used
    pub fn using_proxy(&self) -> bool {
        self.use_proxy
    }

    /// Get the node URL
    pub fn node_url(&self) -> &str {
        &self.node_url
    }

    /// Get the proxy URL (if configured)
    pub fn proxy_url(&self) -> Option<&str> {
        self.proxy_url.as_deref()
    }

    /// Probe and set transport mode (async)
    pub async fn probe_transport(&mut self) {
        // Try direct HTTPS first
        let health_url = format!("{}/health", self.node_url);

        if let Ok(response) = self.client.get(&health_url).send().await {
            if response.status().is_success() {
                tracing::info!("[TRANSPORT] Direct HTTPS to node: OK");
                self.use_proxy = false;
                return;
            }
        }

        // Try proxy if available
        if let Some(proxy_url) = &self.proxy_url {
            let proxy_health = format!("{}/health", proxy_url);
            if let Ok(response) = self.client.get(&proxy_health).send().await {
                if response.status().is_success() {
                    tracing::info!("[TRANSPORT] HTTP proxy at {}: OK", proxy_url);
                    self.use_proxy = true;
                    return;
                }
            }
            tracing::warn!("[TRANSPORT] Proxy {} failed", proxy_url);
        }

        // Fall back to direct HTTPS (may work with self-signed certs)
        tracing::warn!("[TRANSPORT] Falling back to direct HTTPS (verify=False)");
        self.use_proxy = false;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transport_creation() {
        let transport = NodeTransport::new(
            "https://example.com".to_string(),
            None,
            Duration::from_secs(15),
        );
        assert!(transport.is_ok());
    }
}
