# RustChain Kubernetes Deployment

Production-ready Kubernetes manifests for deploying a RustChain node with monitoring.

## Architecture

```
                    ┌─────────────┐
                    │   Ingress   │
                    │ (nginx+TLS) │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼───┐ ┌─────▼─────┐
        │  Dashboard │ │  API  │ │  Grafana  │
        │   :8099    │ │ :8088 │ │   :3000   │
        └─────┬──────┘ └───┬───┘ └─────┬─────┘
              │            │            │
        ┌─────▼────────────▼──┐  ┌─────▼──────┐
        │   RustChain Node    │  │ Prometheus  │
        │  (PVC: data + dl)   │  │ (PVC: 10G) │
        └─────────────────────┘  └─────────────┘
```

## Prerequisites

- Kubernetes 1.24+
- kubectl configured for your cluster
- nginx ingress controller installed
- (Optional) cert-manager for automated TLS

## Quick Start

### Using kustomize

```bash
# Preview what will be applied
kubectl kustomize deploy/kubernetes/

# Deploy everything
kubectl apply -k deploy/kubernetes/
```

### Manual step-by-step

```bash
# 1. Create the namespace
kubectl apply -f deploy/kubernetes/namespace.yaml

# 2. Update secrets with real values
#    Edit secret.yaml and replace all CHANGE_ME placeholders
vim deploy/kubernetes/secret.yaml

# 3. Apply configuration
kubectl apply -f deploy/kubernetes/configmap.yaml
kubectl apply -f deploy/kubernetes/secret.yaml

# 4. Deploy the node
kubectl apply -f deploy/kubernetes/node-deployment.yaml
kubectl apply -f deploy/kubernetes/node-service.yaml

# 5. Deploy monitoring
kubectl apply -f deploy/kubernetes/monitoring-deployment.yaml

# 6. Configure ingress (update hostname first)
kubectl apply -f deploy/kubernetes/ingress.yaml
```

## Configuration

### Secrets

Before deploying, update `secret.yaml` with real values:

| Key | Description |
|-----|-------------|
| `ADMIN_API_KEY` | API key for admin endpoints |
| `ADMIN_WALLET_ADDRESS` | Admin wallet address |
| `ADMIN_PRIVATE_KEY` | Admin wallet private key |
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana admin password |

### Ingress

Edit `ingress.yaml` and replace `rustchain.example.com` with your domain.

For automated TLS with cert-manager, uncomment the `cert-manager.io/cluster-issuer` annotation.

For manual TLS, create the secret:

```bash
kubectl create secret tls rustchain-tls \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key \
  -n rustchain
```

### Node Configuration

Environment variables are managed through `configmap.yaml`. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_HOST` | `0.0.0.0` | Bind address |
| `NODE_PORT` | `8099` | Dashboard port |
| `API_PORT` | `8088` | API port |
| `LOG_LEVEL` | `INFO` | Log verbosity |

## Access

### Dashboard (via NodePort)

```bash
# Get the node IP
kubectl get nodes -o wide

# Access dashboard at http://<node-ip>:30099
# Access API at http://<node-ip>:30088
```

### Grafana

```bash
# Port-forward for local access
kubectl port-forward svc/rustchain-grafana 3000:3000 -n rustchain

# Open http://localhost:3000 (admin / <your-password>)
```

### Prometheus

```bash
kubectl port-forward svc/rustchain-prometheus 9090:9090 -n rustchain
```

## Operations

### Check status

```bash
kubectl get all -n rustchain
kubectl get pvc -n rustchain
```

### View logs

```bash
kubectl logs -f deployment/rustchain-node -n rustchain
kubectl logs -f deployment/rustchain-monitoring -c prometheus -n rustchain
kubectl logs -f deployment/rustchain-monitoring -c grafana -n rustchain
```

### Scale (if running stateless replicas behind a shared DB)

```bash
kubectl scale deployment rustchain-node --replicas=3 -n rustchain
```

### Cleanup

```bash
kubectl delete -k deploy/kubernetes/
```

## Storage

| PVC | Size | Purpose |
|-----|------|---------|
| `rustchain-data-pvc` | 10Gi | SQLite database |
| `rustchain-downloads-pvc` | 5Gi | Downloaded files |
| `prometheus-data-pvc` | 10Gi | Metrics (30d retention) |
| `grafana-data-pvc` | 2Gi | Dashboards and config |
