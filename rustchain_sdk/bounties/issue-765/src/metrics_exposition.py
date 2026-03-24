#!/usr/bin/env python3
"""
Prometheus Metrics Exposition Module - Bounty #765

Provides utilities for generating Prometheus text exposition format
from Python data structures. This module can be used standalone or
as part of the rustchain_exporter.

The Prometheus text exposition format is documented at:
https://github.com/prometheus/docs/blob/main/content/docs/instrumenting/exposition_formats.md
"""

import re
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum


class MetricType(Enum):
    """Prometheus metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    INFO = "info"
    STATE_SET = "stateset"


@dataclass
class Label:
    """A Prometheus label (key-value pair)."""
    name: str
    value: str

    def __post_init__(self):
        # Validate label name
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', self.name):
            raise ValueError(f"Invalid label name: {self.name}")
        # Label names starting with __ are reserved
        if self.name.startswith('__'):
            raise ValueError(f"Label name cannot start with '__': {self.name}")


@dataclass
class MetricSample:
    """A single metric sample with value and labels."""
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp_ms: Optional[int] = None  # Unix timestamp in milliseconds


@dataclass
class MetricFamily:
    """A family of metrics with the same name and type."""
    name: str
    help_text: str
    metric_type: MetricType
    samples: List[MetricSample] = field(default_factory=list)

    def add_sample(self, value: float, labels: Optional[Dict[str, str]] = None,
                   timestamp_ms: Optional[int] = None):
        """Add a sample to this metric family."""
        self.samples.append(MetricSample(
            value=value,
            labels=labels or {},
            timestamp_ms=timestamp_ms
        ))


class PrometheusExposition:
    """
    Generates Prometheus text exposition format output.

    Example usage:
        exposition = PrometheusExposition()
        exposition.add_metric('http_requests_total', 100, {'method': 'GET'},
                             'Total HTTP requests', MetricType.COUNTER)
        print(exposition.render())
    """

    def __init__(self):
        self._families: Dict[str, MetricFamily] = {}

    def clear(self):
        """Clear all metrics."""
        self._families.clear()

    def add_metric(self, name: str, value: float,
                   labels: Optional[Dict[str, str]] = None,
                   help_text: str = "",
                   metric_type: MetricType = MetricType.GAUGE,
                   timestamp_ms: Optional[int] = None):
        """
        Add a metric sample.

        Args:
            name: Metric name (must match [a-zA-Z_:][a-zA-Z0-9_:]*)
            value: Metric value
            labels: Optional label dictionary
            help_text: Help text for the metric
            metric_type: Prometheus metric type
            timestamp_ms: Optional timestamp in milliseconds
        """
        # Validate metric name
        if not re.match(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$', name):
            raise ValueError(f"Invalid metric name: {name}")

        if name not in self._families:
            self._families[name] = MetricFamily(
                name=name,
                help_text=help_text,
                metric_type=metric_type
            )
        else:
            # Update help text if provided
            if help_text:
                self._families[name].help_text = help_text

        self._families[name].add_sample(value, labels, timestamp_ms)

    def add_gauge(self, name: str, value: float,
                  labels: Optional[Dict[str, str]] = None,
                  help_text: str = ""):
        """Add a gauge metric."""
        self.add_metric(name, value, labels, help_text, MetricType.GAUGE)

    def add_counter(self, name: str, value: float,
                    labels: Optional[Dict[str, str]] = None,
                    help_text: str = ""):
        """Add a counter metric."""
        self.add_metric(name, value, labels, help_text, MetricType.COUNTER)

    def add_info(self, name: str, labels: Dict[str, str], help_text: str = ""):
        """
        Add an info metric (convenience for state information).

        Info metrics are gauges with value 1 and labels containing the info.
        """
        self.add_metric(f"{name}_info", 1.0, labels, help_text, MetricType.INFO)

    def add_state_set(self, name: str, states: Dict[str, bool], help_text: str = ""):
        """
        Add a state set metric.

        State sets represent a series of boolean states where exactly one
        is true at a time. Each state becomes a sample with value 1 or 0.
        """
        family_name = name
        if family_name not in self._families:
            self._families[family_name] = MetricFamily(
                name=family_name,
                help_text=help_text,
                metric_type=MetricType.STATE_SET
            )

        for state_name, is_active in states.items():
            labels = {'state': state_name}
            self._families[family_name].add_sample(1.0 if is_active else 0.0, labels)

    def add_histogram(self, name: str, buckets: Dict[float, int],
                      sum_value: float, count: int,
                      labels: Optional[Dict[str, str]] = None,
                      help_text: str = ""):
        """
        Add a histogram metric.

        Args:
            name: Base metric name
            buckets: Dictionary of bucket upper bounds to cumulative counts
            sum_value: Sum of all observed values
            count: Total count of observations
            labels: Optional labels
            help_text: Help text
        """
        base_labels = labels or {}

        # Add bucket samples
        for bound, cumulative_count in sorted(buckets.items()):
            bucket_labels = {**base_labels, 'le': str(bound) if bound != float('inf') else '+Inf'}
            self.add_metric(f"{name}_bucket", float(cumulative_count), bucket_labels,
                           help_text, MetricType.HISTOGRAM)

        # Add sum and count
        self.add_metric(f"{name}_sum", sum_value, base_labels, help_text, MetricType.HISTOGRAM)
        self.add_metric(f"{name}_count", float(count), base_labels, help_text, MetricType.HISTOGRAM)

    def _escape_label_value(self, value: str) -> str:
        """
        Escape special characters in label values.

        Prometheus requires escaping: backslash, double-quote, and line feed.
        """
        return (value
                .replace('\\', '\\\\')
                .replace('"', '\\"')
                .replace('\n', '\\n'))

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus exposition."""
        if not labels:
            return ""

        parts = []
        for key in sorted(labels.keys()):
            value = labels[key]
            escaped_value = self._escape_label_value(str(value))
            parts.append(f'{key}="{escaped_value}"')

        return "{" + ",".join(parts) + "}"

    def render(self) -> str:
        """
        Render all metrics in Prometheus text exposition format.

        Returns:
            String in Prometheus text format suitable for scraping.
        """
        lines = []

        for name in sorted(self._families.keys()):
            family = self._families[name]

            # Add HELP line
            if family.help_text:
                lines.append(f"# HELP {name} {family.help_text}")

            # Add TYPE line
            lines.append(f"# TYPE {name} {family.metric_type.value}")

            # Add samples
            for sample in family.samples:
                labels_str = self._format_labels(sample.labels)
                timestamp_str = ""
                if sample.timestamp_ms is not None:
                    timestamp_str = f" {sample.timestamp_ms}"

                lines.append(f"{name}{labels_str} {sample.value}{timestamp_str}")

        return "\n".join(lines) + "\n"

    def render_family(self, name: str) -> str:
        """Render a single metric family."""
        if name not in self._families:
            return ""

        family = self._families[name]
        lines = []

        if family.help_text:
            lines.append(f"# HELP {name} {family.help_text}")
        lines.append(f"# TYPE {name} {family.metric_type.value}")

        for sample in family.samples:
            labels_str = self._format_labels(sample.labels)
            timestamp_str = ""
            if sample.timestamp_ms is not None:
                timestamp_str = f" {sample.timestamp_ms}"
            lines.append(f"{name}{labels_str} {sample.value}{timestamp_str}")

        return "\n".join(lines) + "\n"


class MetricsCollectorBase:
    """
    Base class for metrics collectors.

    Subclasses should override the `collect` method to gather metrics
    and add them to the exposition object.
    """

    def __init__(self, exposition: Optional[PrometheusExposition] = None):
        self.exposition = exposition or PrometheusExposition()

    def collect(self) -> PrometheusExposition:
        """
        Collect metrics and return the exposition.

        Subclasses should override this method.
        """
        raise NotImplementedError("Subclasses must implement collect()")

    def render(self) -> str:
        """Render collected metrics."""
        return self.exposition.render()


# =============================================================================
# Utility Functions
# =============================================================================

def format_timestamp(dt: Optional[float] = None) -> int:
    """
    Format a timestamp for Prometheus exposition.

    Args:
        dt: Unix timestamp in seconds (default: current time)

    Returns:
        Timestamp in milliseconds
    """
    if dt is None:
        dt = time.time()
    return int(dt * 1000)


def validate_metric_name(name: str) -> bool:
    """Validate a Prometheus metric name."""
    return bool(re.match(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$', name))


def validate_label_name(name: str) -> bool:
    """Validate a Prometheus label name."""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        return False
    if name.startswith('__'):
        return False
    return True


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == '__main__':
    # Example: Create metrics exposition
    exposition = PrometheusExposition()

    # Add some example metrics
    exposition.add_gauge(
        'example_temperature_celsius',
        23.5,
        {'location': 'office', 'sensor': 'temp_01'},
        'Current temperature in Celsius'
    )

    exposition.add_counter(
        'example_requests_total',
        1024,
        {'method': 'GET', 'endpoint': '/api/users'},
        'Total number of requests'
    )

    exposition.add_info(
        'example_app',
        {'version': '1.0.0', 'environment': 'production'},
        'Application information'
    )

    exposition.add_state_set(
        'example_status',
        {'running': True, 'stopped': False, 'error': False},
        'Current application status'
    )

    exposition.add_histogram(
        'example_request_duration_seconds',
        {0.01: 100, 0.05: 500, 0.1: 800, 0.5: 950, 1.0: 990, float('inf'): 1000},
        125.5,
        1000,
        {'handler': 'api'},
        'Request duration in seconds'
    )

    print(exposition.render())
