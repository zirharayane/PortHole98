"""Unit tests for check-host.net defensive parsing, node selection, and latency stats."""

import pytest
from app.services.checkhost import CheckHostService
from app.utils.stats import calculate_latency_stats


def test_calculate_latency_stats_basic():
    """Verify median, min, max, and failed count calculation on normal samples."""
    samples = [10.0, 20.0, 30.0]
    median, min_val, max_val, failed = calculate_latency_stats(samples, failed_count=1)
    assert median == 20.0
    assert min_val == 10.0
    assert max_val == 30.0
    assert failed == 1


def test_calculate_latency_stats_even_samples():
    """Verify median calculation with an even number of samples."""
    samples = [10.0, 20.0, 30.0, 40.0]
    median, min_val, max_val, failed = calculate_latency_stats(samples, failed_count=0)
    assert median == 25.0
    assert min_val == 10.0
    assert max_val == 40.0
    assert failed == 0


def test_calculate_latency_stats_empty():
    """Verify stats when all attempts failed."""
    median, min_val, max_val, failed = calculate_latency_stats([], failed_count=3)
    assert median is None
    assert min_val is None
    assert max_val is None
    assert failed == 3


def test_calculate_latency_stats_single():
    """Verify stats with exactly one sample."""
    median, min_val, max_val, failed = calculate_latency_stats([55.456], failed_count=0)
    assert median == 55.46
    assert min_val == 55.46
    assert max_val == 55.46
    assert failed == 0


def test_checkhost_parse_success():
    """Defensive parser handles standard success payload with time in seconds."""
    service = CheckHostService()
    raw = [{"address": "1.1.1.1", "time": 0.04512}]
    status, latency = service.parse_node_result(raw)
    assert status == "Open"
    assert latency == 45.12


def test_checkhost_parse_timeout_error():
    """Defensive parser handles timeout error string."""
    service = CheckHostService()
    raw = [{"error": "Connection timed out"}]
    status, latency = service.parse_node_result(raw)
    assert status == "Connection timed out"
    assert latency is None


def test_checkhost_parse_connection_refused():
    """Defensive parser handles connection refused error string."""
    service = CheckHostService()
    raw = [{"error": "Connection refused"}]
    status, latency = service.parse_node_result(raw)
    assert status == "Connection refused"
    assert latency is None


def test_checkhost_parse_pending_null():
    """Defensive parser handles pending null status during in-flight checks."""
    service = CheckHostService()
    status, latency = service.parse_node_result(None)
    assert status == "pending"
    assert latency is None


def test_checkhost_parse_malformed_shapes():
    """Defensive parser handles arbitrary/unexpected payloads without crashing."""
    service = CheckHostService()

    # Empty list
    assert service.parse_node_result([]) == ("unknown", None)

    # List with unexpected dict
    assert service.parse_node_result([{"foo": "bar"}]) == ("unknown", None)

    # Empty dict
    assert service.parse_node_result({}) == ("unknown", None)

    # Dict without time/error
    assert service.parse_node_result({"status": 200}) == ("unknown", None)

    # Unexpected types
    assert service.parse_node_result(42) == ("unknown", None)
    assert service.parse_node_result(True) == ("unknown", None)
    assert service.parse_node_result("arbitrary_string") == ("unknown", None)
