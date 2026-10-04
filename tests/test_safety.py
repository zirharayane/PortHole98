"""Unit tests for security guards, subnet validation, and rate limiting."""

import pytest
from fastapi import HTTPException
from app.services.safety import (
    InMemoryRateLimiter,
    validate_private_subnet,
    validate_public_target,
)


def test_validate_private_subnet_allowed():
    """Verify that RFC 1918 private subnets <= /24 are permitted."""
    valid_subnets = [
        "10.0.0.0/24",
        "10.50.100.0/25",
        "172.16.1.0/24",
        "172.31.255.0/28",
        "192.168.1.0/24",
        "192.168.100.0/26",
        "192.168.1.50/32",
    ]
    for s in valid_subnets:
        net = validate_private_subnet(s)
        assert net.prefixlen >= 24


def test_validate_private_subnet_reject_public():
    """Verify that public IP ranges are strictly rejected with HTTP 400."""
    public_subnets = [
        "8.8.8.0/24",
        "1.1.1.0/24",
        "142.250.190.0/24",
        "203.0.113.0/24",
    ]
    for s in public_subnets:
        with pytest.raises(HTTPException) as exc_info:
            validate_private_subnet(s)
        assert exc_info.value.status_code == 400
        assert "private" in exc_info.value.detail.lower()


def test_validate_private_subnet_reject_large_ranges():
    """Verify that subnets larger than /24 (e.g. /16 or /8) are rejected with HTTP 400."""
    large_subnets = [
        "10.0.0.0/8",
        "10.0.0.0/16",
        "10.0.0.0/23",
        "172.16.0.0/12",
        "172.16.0.0/20",
        "192.168.0.0/16",
        "192.168.0.0/22",
    ]
    for s in large_subnets:
        with pytest.raises(HTTPException) as exc_info:
            validate_private_subnet(s)
        assert exc_info.value.status_code == 400
        assert "capped at /24" in exc_info.value.detail.lower()


def test_validate_private_subnet_invalid_input():
    """Verify that malformed or empty inputs raise HTTP 400."""
    invalid_inputs = ["", "   ", "not-a-subnet", "192.168.1.300/24", "999.999.999.999/24"]
    for s in invalid_inputs:
        with pytest.raises(HTTPException) as exc_info:
            validate_private_subnet(s)
        assert exc_info.value.status_code == 400


def test_validate_public_target_enforcement():
    """Verify that public target IP must strictly match verified public IP."""
    # Matches -> passes
    validate_public_target("102.97.50.160", "102.97.50.160")

    # Mismatch -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        validate_public_target("8.8.8.8", "102.97.50.160")
    assert exc_info.value.status_code == 403

    # Missing public IP -> 400 Bad Request
    with pytest.raises(HTTPException) as exc_info:
        validate_public_target("102.97.50.160", "")
    assert exc_info.value.status_code == 400


def test_rate_limiter_sliding_window():
    """Verify sliding-window rate limiter permits 5 requests and blocks the 6th."""
    limiter = InMemoryRateLimiter(limit=5, window_seconds=60.0)
    client_ip = "192.168.1.100"

    # First 5 calls pass
    for _ in range(5):
        limiter.check(client_ip)

    # 6th call raises HTTP 429
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(client_ip)
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail

    # Separate client IP is unaffected
    other_ip = "192.168.1.101"
    limiter.check(other_ip)
