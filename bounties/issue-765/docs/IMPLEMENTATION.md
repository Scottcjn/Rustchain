# Implementation Details - Bounty #765

This document describes the architecture and design decisions for the RustChain Prometheus Exporter.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     RustChain Prometheus Exporter                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   HTTP       │    │   Metrics    │    │   Node       │      │
│  │   Server     │◄──►│   Registry   │◄──►│   Client     │      │
│  │  (port 9100) │    │              │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Prometheus  │    │  Exposition  │    │  RustChain   │      │
│  │   Scraper    │    │   Format     │    │    Node      │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. ExporterConfig

Configuration management with environment variable support:

```python
@dataclass
class ExporterConfig:
    node_url: str = "https://rustchain.org"
    exporter_port: int = 9100
    scrape_interval: int = 30
    tls_verify: bool = True
    tls_ca_bundle: Optional[str] = None
    request_timeout: float = 10.0
    max_retries: int = 3
```

**Design Decisions**:
- Uses dataclass for immutability and clear defaults
- Environment variables override defaults
- TLS CA bundle support for custom certificates

### 2. MetricsRegistry

Thread-safe metrics storage with Prometheus exposition support:

```python
class MetricsRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        self._metrics: Dict[str, List[MetricSample]] = {}
        self._metadata: Dict[str, Dict[str, str]] = {}
```

**Key Features**:
- Thread-safe with reentrant lock
- Stores metric metadata (help text, type)
- Supports timestamps for pushgateway use cases
- Label value escaping per Prometheus spec

**Prometheus Format Compliance**:
```
# HELP metric_name Description text
# TYPE metric_name gauge
metric_name{label="value"} 42.0 1234567890123
```

### 3. RustChainNodeClient

HTTP client for fetching node data with retry logic:

```python
class RustChainNodeClient:
    def _fetch_json(self, endpoint: str) -> Optional[Dict]:
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.get(url, ...)
                return response.json()
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(backoff)
```

**Retry Strategy**:
- Exponential backoff: `backoff * 2^attempt`
- Configurable max retries (default: 3)
- Separate handling for Timeout, ConnectionError, RequestException

**Endpoints**:
- `/health` - Node health status
- `/epoch` - Epoch and network stats
- `/api/miners` - Active miner list

### 4. MetricsCollector

Orchestrates metric collection from node APIs:

```python
class MetricsCollector:
    def collect(self) -> bool:
        # 1. Clear previous metrics
        self.registry.clear()
        
        # 2. Fetch and collect health
        health = self.client.get_health()
        self._collect_health(health)
        
        # 3. Fetch and collect epoch
        epoch = self.client.get_epoch()
        self._collect_epoch(epoch)
        
        # 4. Fetch and collect miners
        miners = self.client.get_miners()
        self._collect_miners(miners)
        
        # 5. Record scrape performance
        self._record_scrape_metrics()
```

**Collection Strategy**:
- Atomic collection (all or nothing)
- Clears registry before each collection
- Records scrape duration and error counts
- Returns success/failure status

### 5. ExporterServer

Main server with background collection thread:

```python
class ExporterServer:
    def start(self):
        # Start background collection thread
        self._collection_thread = threading.Thread(
            target=self._collection_loop, daemon=True
        )
        self._collection_thread.start()
        
        # Start HTTP server
        self.server = HTTPServer((host, port), MetricsHandler)
        self.server.serve_forever()
```

**Threading Model**:
- Background thread for metrics collection
- Main thread for HTTP server
- Graceful shutdown support

### 6. MetricsHandler

HTTP request handler for Prometheus scraping:

```python
class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if path == '/metrics':
            self._serve_metrics()
        elif path == '/health':
            self._serve_health()
        elif path == '/':
            self._serve_index()
```

**Endpoints**:
- `/metrics` - Prometheus text format (Content-Type: `text/plain; version=0.0.4`)
- `/health` - JSON health status
- `/` - HTML index page

## Metrics Exposition Module

The `metrics_exposition.py` module provides standalone Prometheus format generation:

### Metric Types Supported

1. **Gauge**: Point-in-time values (temperature, count)
2. **Counter**: Monotonically increasing values (requests, errors)
3. **Info**: State information (version, build info)
4. **StateSet**: Boolean states (running/stopped/error)
5. **Histogram**: Distribution buckets (latency, size)

### Example Usage

```python
from metrics_exposition import PrometheusExposition, MetricType

exp = PrometheusExposition()

# Histogram for request latency
exp.add_histogram(
    'request_duration_seconds',
    buckets={0.01: 100, 0.05: 500, 0.1: 800, float('inf'): 1000},
    sum_value=125.5,
    count=1000
)

# State set for application status
exp.add_state_set(
    'app_status',
    {'running': True, 'stopped': False, 'error': False}
)
```

## Error Handling

### Node Communication Errors

```python
try:
    response = self.session.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
except Timeout:
    logger.warning("Request timed out")
except ConnectionError:
    logger.warning("Connection failed")
except RequestException as e:
    logger.error(f"Request error: {e}")
```

### Graceful Degradation

- Failed endpoint → Skip metric, continue collection
- All endpoints fail → Return last known metrics or empty
- HTTP server errors → Log and continue

## Performance Considerations

### Memory Management

- Metrics cleared before each collection
- No historical data stored (Prometheus handles retention)
- Minimal object allocation in hot path

### Concurrency

- Read-write lock for metrics registry
- Background collection doesn't block HTTP requests
- Thread-safe label dictionary handling

### Network Efficiency

- Reused requests.Session for connection pooling
- Configurable timeouts prevent hanging
- Exponential backoff prevents thundering herd

## Testing Strategy

### Unit Tests

- Configuration parsing
- Metrics registry operations
- Exposition format generation
- Label escaping

### Integration Tests

- Full collection cycle with mocked node
- HTTP endpoint responses
- Error scenarios

### Mocking Strategy

```python
@patch('rustchain_exporter.RustChainNodeClient')
def test_collection(mock_client_class):
    mock_client = MagicMock()
    mock_client.get_health.return_value = NodeHealth(ok=True, ...)
    mock_client.get_epoch.return_value = EpochInfo(epoch=100, ...)
    mock_client.get_miners.return_value = [MinerInfo(...)]
    
    collector = MetricsCollector(config, registry)
    success = collector.collect()
    
    assert success is True
```

## Security Considerations

### TLS Configuration

```python
def get_verify_setting(self) -> Any:
    if self.tls_ca_bundle:
        return self.tls_ca_bundle  # Custom CA
    return self.tls_verify  # Boolean
```

### Admin Key Handling

- Read from environment variable only
- Never logged or exposed in metrics
- Optional (only needed for admin endpoints)

### Container Security

- Non-root user in Docker image
- Minimal base image (python:slim)
- No unnecessary packages

## Extensibility

### Adding New Metrics

1. Add metric to `MetricsCollector._collect_*` method
2. Update documentation
3. Add alerting rules if applicable
4. Update tests

### Adding New Endpoints

1. Add fetch method to `RustChainNodeClient`
2. Add dataclass for response type
3. Add collection method to `MetricsCollector`
4. Update main `collect()` method

### Custom Collectors

```python
from rustchain_exporter import MetricsCollector, MetricsRegistry

class CustomMetricsCollector(MetricsCollector):
    def collect(self) -> bool:
        # Call parent for standard metrics
        super().collect()
        
        # Add custom metrics
        self.registry.add_gauge(
            'custom_metric',
            self._fetch_custom_data()
        )
        
        return True
```

## Monitoring the Exporter

The exporter exposes self-monitoring metrics:

- `rustchain_scrape_duration_seconds` - Collection performance
- `rustchain_scrapes_total` - Total collections
- `rustchain_scrape_errors_total` - Error count
- `rustchain_last_scrape_timestamp` - Freshness indicator

### Health Check

```bash
curl http://localhost:9100/health

{
  "status": "healthy",
  "scrape_count": 150,
  "error_count": 0,
  "last_scrape_duration": 0.523
}
```

## Future Enhancements

Potential improvements for future versions:

1. **Pushgateway Support**: Push metrics instead of pull
2. **Histograms**: Native histogram support for latency metrics
3. **Service Discovery**: Kubernetes SD config
4. **Authentication**: HTTP basic auth for metrics endpoint
5. **Rate Limiting**: Protect against aggressive scraping
6. **Multi-node**: Aggregate metrics from multiple nodes
