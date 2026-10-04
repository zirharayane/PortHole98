"""Unit tests for Carrier-Grade NAT (CGNAT) detection and IP classification."""

import pytest
from app.services.network_info import classify_cgnat


def test_matching_public_ip():
    """Matching public WAN IP and public IPv4 indicates no CGNAT."""
    cgnat, reason = classify_cgnat("203.0.113.195", "203.0.113.195")
    assert cgnat is False
    assert "matches public" in reason.lower()


def test_mismatched_wan_ip():
    """Mismatch between router WAN IP and public IPv4 indicates upstream translation."""
    cgnat, reason = classify_cgnat("203.0.113.195", "198.51.100.42")
    assert cgnat is True
    assert "does not match" in reason.lower()


def test_rfc6598_cgnat_space():
    """WAN IP in 100.64.0.0/10 indicates Carrier-Grade NAT."""
    # Boundary tests in 100.64.0.0/10
    test_ips = ["100.64.0.1", "100.100.50.25", "100.127.255.254"]
    for ip in test_ips:
        cgnat, reason = classify_cgnat("203.0.113.195", ip)
        assert cgnat is True
        assert "100.64.0.0/10" in reason


def test_rfc1918_private_wan_ip():
    """WAN IP in RFC 1918 private ranges indicates double NAT / upstream NAT."""
    private_ips = [
        "10.0.0.1",
        "10.254.1.1",
        "172.16.0.1",
        "172.31.255.254",
        "192.168.0.1",
        "192.168.1.1",
        "192.168.178.1",
    ]
    for ip in private_ips:
        cgnat, reason = classify_cgnat("203.0.113.195", ip)
        assert cgnat is True
        assert "RFC 1918" in reason


def test_missing_router_wan_ip():
    """When router WAN IP is unavailable, CGNAT is false and reasons prompt manual entry."""
    cgnat, reason = classify_cgnat("203.0.113.195", None)
    assert cgnat is False
    assert "unavailable" in reason.lower()


def test_missing_both_ips():
    """When both public IPv4 and WAN IP are unavailable."""
    cgnat, reason = classify_cgnat(None, None)
    assert cgnat is False


def test_invalid_ip_format():
    """Invalid WAN IP string returns False without crashing."""
    cgnat, reason = classify_cgnat("203.0.113.195", "not-an-ip")
    assert cgnat is False
    assert "invalid" in reason.lower()
