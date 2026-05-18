"""Prometheus metrics for MCP Server"""

import logging
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

logger = logging.getLogger(__name__)

# Define metrics
ERP_QUERY_COUNT = Counter(
    "erp_query_count",
    "Total ERP query operations",
    ["form_id", "status"],
)

ERP_CREATE_COUNT = Counter(
    "erp_create_count",
    "Total ERP create operations",
    ["form_id", "status"],
)

ERP_ERROR_COUNT = Counter(
    "erp_error_count",
    "Total ERP operation errors",
    ["operation", "error_type"],
)

ERP_LATENCY = Histogram(
    "erp_operation_latency_seconds",
    "ERP operation latency in seconds",
    ["operation"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# Cache Metrics
CACHE_HIT_COUNT = Counter(
    "cache_hit_count",
    "Total number of cache hits"
)

CACHE_MISS_COUNT = Counter(
    "cache_miss_count",
    "Total number of cache misses"
)

CACHE_SIZE = Gauge(
    "cache_size",
    "Current number of cached entries"
)

CACHE_HIT_RATE = Gauge(
    "cache_hit_rate",
    "Cache hit rate (0-1)"
)


def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


def record_query(form_id: str, success: bool) -> None:
    """Record query operation"""
    status = "success" if success else "failure"
    ERP_QUERY_COUNT.labels(form_id=form_id, status=status).inc()


def record_create(form_id: str, success: bool) -> None:
    """Record create operation"""
    status = "success" if success else "failure"
    ERP_CREATE_COUNT.labels(form_id=form_id, status=status).inc()


def record_error(operation: str, error_type: str) -> None:
    """Record error"""
    ERP_ERROR_COUNT.labels(operation=operation, error_type=error_type).inc()


def record_cache_hit() -> None:
    """Record cache hit"""
    CACHE_HIT_COUNT.inc()


def record_cache_miss() -> None:
    """Record cache miss"""
    CACHE_MISS_COUNT.inc()


def update_cache_metrics(stats: dict) -> None:
    """Update cache metrics from stats"""
    CACHE_SIZE.set(stats.get("size", 0))
    CACHE_HIT_RATE.set(stats.get("hit_rate", 0))