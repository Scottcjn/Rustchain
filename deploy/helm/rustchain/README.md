# RustChain Helm Chart

Helm chart for deploying a RustChain Proof-of-Antiquity blockchain node on Kubernetes.

## Prerequisites

- Kubernetes 1.23+
- Helm 3.x
- A container image of RustChain pushed to a registry (see [Building the Image](#building-the-image))

## Building the Image

From the repository root:

```bash
docker build -t ghcr.io/celebritypunks/rustchain:latest .
docker push ghcr.io/celebritypunks/rustchain:latest
```

## Installing the Chart

```bash
helm install rustchain ./deploy/helm/rustchain
```

With custom values:

```bash
helm install rustchain ./deploy/helm/rustchain -f my-values.yaml
```

## Uninstalling

```bash
helm uninstall rustchain
```

> PersistentVolumeClaims are not deleted automatically. To remove all data:
> `kubectl delete pvc -l app.kubernetes.io/name=rustchain`

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of pod replicas | `1` |
| `image.repository` | Container image repository | `ghcr.io/celebritypunks/rustchain` |
| `image.tag` | Container image tag | `latest` |
| `rustchain.logLevel` | Application log level | `INFO` |
| `rustchain.dashboardPort` | Dashboard HTTP port | `8099` |
| `rustchain.apiPort` | API endpoint port | `8088` |
| `persistence.data.enabled` | Enable persistent storage for chain data | `true` |
| `persistence.data.size` | Size of the data volume | `10Gi` |
| `persistence.downloads.enabled` | Enable persistent storage for downloads | `true` |
| `persistence.downloads.size` | Size of the downloads volume | `5Gi` |
| `ingress.enabled` | Enable Ingress resource | `false` |
| `ingress.className` | Ingress class name | `nginx` |
| `resources.limits.cpu` | CPU limit | `1` |
| `resources.limits.memory` | Memory limit | `1Gi` |
| `resources.requests.cpu` | CPU request | `250m` |
| `resources.requests.memory` | Memory request | `256Mi` |
| `secrets.githubToken` | GitHub API token (stored as Secret) | `""` |
| `secrets.tipBotWallet` | Tip bot wallet address (stored as Secret) | `""` |

## Enabling Ingress

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: rustchain.example.com
      paths:
        - path: /
          pathType: Prefix
          servicePort: 8099
  tls:
    - secretName: rustchain-tls
      hosts:
        - rustchain.example.com
```

## Persistence

The chart creates two PVCs by default:

- **data** (`10Gi`) -- SQLite database and chain state at `/rustchain/data`
- **downloads** (`5Gi`) -- Downloaded artifacts at `/rustchain/downloads`

The Deployment uses `strategy: Recreate` to avoid volume mount conflicts with SQLite.

## Security

- Runs as non-root user (UID 1000)
- Drops all Linux capabilities
- Secrets are base64-encoded in a Kubernetes Secret resource
- Pass sensitive values via `--set secrets.githubToken=<token>` rather than committing them to `values.yaml`
