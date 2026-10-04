"""Network information discovery, UPnP WAN IP detection, and CGNAT classification."""

import ipaddress
import logging
import socket
from typing import Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

# RFC 6598 Shared Address Space (Carrier-Grade NAT)
CGNAT_NETWORK = ipaddress.IPv4Network("100.64.0.0/10")

# RFC 1918 Private Address Spaces
RFC1918_NETWORKS = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)


def is_rfc1918(ip_obj: ipaddress.IPv4Address) -> bool:
    """Return True if the IPv4 address falls within RFC 1918 private space."""
    return any(ip_obj in net for net in RFC1918_NETWORKS)


def detect_local_subnet() -> Optional[str]:
    """Detect active local private IPv4 interface and return its /24 subnet CIDR."""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Does not send actual packets, just selects the outbound routing interface
        s.connect(("1.1.1.1", 80))
        local_ip = s.getsockname()[0]
        ip_obj = ipaddress.ip_address(local_ip)
        if isinstance(ip_obj, ipaddress.IPv4Address) and is_rfc1918(ip_obj):
            net = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            return str(net)
    except Exception as exc:
        logger.debug("Failed to detect local subnet via socket routing: %s", exc)
    finally:
        if s is not None:
            s.close()
    return "192.168.1.0/24"


_cached_ipv4: Optional[Tuple[float, str]] = None


async def get_public_ipv4(client: Optional[httpx.AsyncClient] = None, force_refresh: bool = False) -> Optional[str]:
    """Fetch public IPv4 from api.ipify.org, with 60s memory caching for stability."""
    global _cached_ipv4
    import time
    now = time.monotonic()
    if not force_refresh and _cached_ipv4 is not None:
        cache_time, ip = _cached_ipv4
        if now - cache_time < 60.0:
            return ip

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=5.0)
        should_close = True

    try:
        resp = await client.get("https://api.ipify.org?format=json")
        if resp.status_code == 200:
            data = resp.json()
            ip_str = data.get("ip")
            if ip_str:
                ipaddress.IPv4Address(ip_str)
                _cached_ipv4 = (now, ip_str)
                return ip_str
    except Exception as exc:
        logger.debug("Primary IPv4 provider failed, trying secondary: %s", exc)
        try:
            resp = await client.get("https://api4.ipify.org?format=json")
            if resp.status_code == 200:
                data = resp.json()
                ip_str = data.get("ip")
                if ip_str:
                    ipaddress.IPv4Address(ip_str)
                    _cached_ipv4 = (now, ip_str)
                    return ip_str
        except Exception as exc2:
            logger.warning("All IPv4 discovery providers failed: %s", exc2)
            if _cached_ipv4 is not None:
                return _cached_ipv4[1]
    finally:
        if should_close:
            await client.aclose()
    return _cached_ipv4[1] if _cached_ipv4 else None


async def get_public_ipv6(client: Optional[httpx.AsyncClient] = None) -> Optional[str]:
    """Fetch public IPv6 from api64.ipify.org; returns None if unavailable or IPv4-only."""
    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=4.0)
        should_close = True

    try:
        resp = await client.get("https://api64.ipify.org?format=json")
        if resp.status_code == 200:
            data = resp.json()
            ip_str = data.get("ip")
            if ip_str:
                ip_obj = ipaddress.ip_address(ip_str)
                if isinstance(ip_obj, ipaddress.IPv6Address):
                    return ip_str
    except Exception as exc:
        logger.debug("IPv6 discovery failed or not supported by network: %s", exc)
    finally:
        if should_close:
            await client.aclose()
    return None


def get_router_wan_ip_upnp() -> Optional[str]:
    """Query UPnP IGD for router WAN IP using miniupnpc, if installed and router responds."""
    try:
        import miniupnpc  # type: ignore[import-untyped]
    except ImportError:
        logger.info("miniupnpc is not installed; UPnP WAN IP detection disabled.")
        return None

    try:
        u = miniupnpc.UPnP()
        u.discoverdelay = 200
        devices = u.discover()
        if devices > 0:
            u.selectigd()
            ext_ip = u.externalipaddress()
            if ext_ip and ext_ip != "0.0.0.0":
                ipaddress.ip_address(ext_ip)
                return ext_ip
    except Exception as exc:
        logger.debug("UPnP IGD WAN IP query failed: %s", exc)
    return None


def classify_cgnat(public_ipv4: Optional[str], router_wan_ip: Optional[str]) -> Tuple[bool, str]:
    """
    Determine whether Carrier-Grade NAT (CGNAT) or double-NAT is active.

    Returns:
        (cgnat_detected: bool, reason: str)
    """
    if not router_wan_ip:
        if public_ipv4:
            return False, "Router WAN IP unavailable via UPnP. Enter WAN IP manually to verify CGNAT status."
        return False, "Public IP and router WAN IP are both unavailable."

    # Validate router_wan_ip format
    try:
        wan_obj = ipaddress.ip_address(router_wan_ip)
    except ValueError:
        return False, f"Invalid router WAN IP address format: {router_wan_ip}"

    # Check 1: Is WAN IP in 100.64.0.0/10 (RFC 6598 Carrier-Grade NAT)?
    if isinstance(wan_obj, ipaddress.IPv4Address) and wan_obj in CGNAT_NETWORK:
        return True, f"Router WAN IP ({router_wan_ip}) is in RFC 6598 Carrier-Grade NAT space (100.64.0.0/10)."

    # Check 2: Is WAN IP a private RFC 1918 address?
    if isinstance(wan_obj, ipaddress.IPv4Address) and is_rfc1918(wan_obj):
        return True, f"Router WAN IP ({router_wan_ip}) is an RFC 1918 private address, indicating an upstream NAT/CGNAT layer."

    # Check 3: If public_ipv4 is available, does it differ from router_wan_ip?
    if public_ipv4 and public_ipv4 != router_wan_ip:
        return True, (
            f"Router WAN IP ({router_wan_ip}) does not match detected public IPv4 ({public_ipv4}), "
            "indicating upstream translation (CGNAT or ISP proxy)."
        )

    # If public and WAN IP match and are public
    if public_ipv4 and public_ipv4 == router_wan_ip:
        return False, f"Router WAN IP matches public IPv4 ({public_ipv4}). No CGNAT detected."

    return False, "WAN IP appears to be public, but public IPv4 could not be verified."
