"""Safety guards, rate limiting, and subnet boundary validation."""

import ipaddress
import time
from collections import defaultdict
from typing import Dict, List
from fastapi import HTTPException, Request

# RFC 1918 Private IPv4 Networks
ALLOWED_PRIVATE_NETWORKS = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter per client IP."""

    def __init__(self, limit: int = 5, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def check(self, client_ip: str) -> None:
        """
        Record a request attempt for client_ip.
        Raises HTTPException(429) if the rate limit is exceeded.
        """
        now = time.monotonic()
        timestamps = self._requests[client_ip]

        # Evict timestamps older than sliding window
        cutoff = now - self.window_seconds
        self._requests[client_ip] = [t for t in timestamps if t > cutoff]

        if len(self._requests[client_ip]) >= self.limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: maximum {self.limit} trigger requests per minute."
            )

        self._requests[client_ip].append(now)


# Global rate limiter instance (5 per minute per client)
rate_limiter = InMemoryRateLimiter(limit=5, window_seconds=60.0)


def get_client_ip(request: Request) -> str:
    """Extract client IP address from FastAPI request."""
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def validate_private_subnet(subnet_str: str) -> ipaddress.IPv4Network:
    """
    Validate that a given subnet string is a valid private RFC 1918 IPv4 network
    and does not exceed the /24 size limit.

    Raises:
        HTTPException(400) if invalid, public, or larger than /24.
    """
    if not subnet_str or not subnet_str.strip():
        raise HTTPException(status_code=400, detail="Subnet CIDR cannot be empty.")

    try:
        net = ipaddress.IPv4Network(subnet_str.strip(), strict=False)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid IPv4 subnet format: {exc}"
        ) from exc

    # Enforce maximum subnet size: prefix length must be >= 24 (e.g. /24, /25... up to /32)
    if net.prefixlen < 24:
        raise HTTPException(
            status_code=400,
            detail=f"Subnet size /{net.prefixlen} is too large. Local scans are capped at /24 (max 256 addresses)."
        )

    # Must be contained within RFC 1918 private ranges
    is_private_allowed = any(
        net.network_address in allowed_net and net.broadcast_address in allowed_net
        for allowed_net in ALLOWED_PRIVATE_NETWORKS
    )

    if not is_private_allowed:
        raise HTTPException(
            status_code=400,
            detail="Local scans only accept private RFC 1918 ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)."
        )

    return net


def validate_public_target(target_ip: str, verified_public_ip: str) -> None:
    """
    Enforce that the target IP for public reachability testing strictly matches
    the verified public IP detected by network discovery, preventing arbitrary scanning.
    """
    if not verified_public_ip:
        raise HTTPException(
            status_code=400,
            detail="Public IPv4 could not be verified on this network. Cannot run public check."
        )

    if target_ip.strip() != verified_public_ip.strip():
        raise HTTPException(
            status_code=403,
            detail="Public checks can only target this machine's verified public IP address."
        )
