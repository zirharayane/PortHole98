"""Local network TCP connect scanner with two-stage discovery, concurrency controls, and service identification."""

import asyncio
import ipaddress
import logging
import socket
import uuid
from typing import Dict, List, Optional, Set, Tuple

from app.config import settings
from app.models import DeviceResult, LocalScanStatusResponse, OpenPort

logger = logging.getLogger(__name__)

# Common TCP ports profile (including 25565)
COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 135, 139, 143,
    443, 445, 993, 995, 1433, 3306, 3389, 5432, 8080, 8443, 25565,
]

# Top 1024 ports profile
TOP1024_PORTS = list(range(1, 1025))

# Common service names fallback dictionary
KNOWN_SERVICES = {
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    53: "domain",
    80: "http",
    110: "pop3",
    135: "msrpc",
    139: "netbios-ssn",
    143: "imap",
    443: "https",
    445: "microsoft-ds",
    993: "imaps",
    995: "pop3s",
    1433: "ms-sql-s",
    3306: "mysql",
    3389: "ms-wbt-server",
    5432: "postgresql",
    8080: "http-alt",
    8443: "https-alt",
    25565: "minecraft",
}

# Quick discovery ports to probe during Stage 1
DISCOVERY_PORTS = [80, 443, 445, 135, 22, 53, 8080, 3389, 21, 25565]


def guess_service_name(port: int) -> str:
    """Guess service name using socket.getservbyport with fallback to known dictionary."""
    try:
        return socket.getservbyport(port, "tcp")
    except (OSError, socket.error):
        return KNOWN_SERVICES.get(port, "unknown")


async def resolve_hostname(ip: str) -> Optional[str]:
    """Resolve reverse DNS hostname asynchronously with timeout."""
    def _lookup() -> Optional[str]:
        try:
            name, _, _ = socket.gethostbyaddr(ip)
            return name
        except Exception:
            return None

    try:
        return await asyncio.wait_for(asyncio.to_thread(_lookup), timeout=1.0)
    except Exception:
        return None


async def probe_port(
    ip: str,
    port: int,
    semaphore: asyncio.Semaphore,
    timeout: float = 0.5,
) -> Tuple[bool, bool]:
    """
    Attempt TCP connect to ip:port.

    Returns:
        (is_open: bool, is_host_alive: bool)
        If connection succeeds: (True, True)
        If ConnectionRefusedError: (False, True) -> TCP RST proves host is alive!
        If Timeout / HostUnreachable: (False, False)
    """
    async with semaphore:
        try:
            conn = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(conn, timeout=timeout)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True, True
        except ConnectionRefusedError:
            # Host actively sent TCP RST -> host is alive
            return False, True
        except (asyncio.TimeoutError, OSError):
            return False, False


class LocalScanService:
    """Coordinates two-stage network scanning and tracking of background jobs."""

    def __init__(self) -> None:
        self._jobs: Dict[str, LocalScanStatusResponse] = {}

    def get_job(self, job_id: str) -> Optional[LocalScanStatusResponse]:
        """Retrieve local scan job status."""
        return self._jobs.get(job_id)

    async def _discover_live_hosts(
        self,
        target_ips: List[str],
        semaphore: asyncio.Semaphore,
        timeout: float,
        live_open_ports: Dict[str, Set[int]],
    ) -> Set[str]:
        """Stage 1: Rapid host discovery using common ports."""
        live_hosts: Set[str] = set()

        async def _check_target(ip: str, port: int) -> None:
            is_open, is_alive = await probe_port(ip, port, semaphore, timeout=timeout)
            if is_alive:
                live_hosts.add(ip)
            if is_open:
                live_open_ports[ip].add(port)

        tasks = [
            _check_target(ip, port)
            for ip in target_ips
            for port in DISCOVERY_PORTS
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        return live_hosts

    async def _execute_scan(
        self,
        job_id: str,
        subnet_network: ipaddress.IPv4Network,
        port_profile: str,
    ) -> None:
        """Background worker executing Stage 1 (host discovery) and Stage 2 (port scan)."""
        semaphore = asyncio.Semaphore(settings.local_scan_semaphore)
        timeout = settings.local_scan_timeout

        target_ports = COMMON_PORTS if port_profile == "common" else TOP1024_PORTS
        # Generate usable host IP addresses
        if subnet_network.num_addresses <= 2:
            target_ips = [str(ip) for ip in subnet_network]
        else:
            target_ips = [str(ip) for ip in subnet_network.hosts()]

        live_open_ports: Dict[str, Set[int]] = {ip: set() for ip in target_ips}

        try:
            # Stage 1: Host discovery (0% -> 30% progress)
            self._jobs[job_id].progress = 10
            live_hosts = await self._discover_live_hosts(target_ips, semaphore, timeout, live_open_ports)
            self._jobs[job_id].progress = 30

            # If no live hosts discovered through probe ports, fallback to scanning all targets if subnet <= 32 hosts
            if not live_hosts and len(target_ips) <= 32:
                live_hosts = set(target_ips)

            # Stage 2: Port scanning only on live hosts (30% -> 90% progress)
            total_stage2_probes = len(live_hosts) * len(target_ports)
            probes_completed = 0

            async def _scan_host_port(ip: str, port: int) -> None:
                nonlocal probes_completed
                # If port was already found open during Stage 1 discovery, skip redundant probe
                if port not in live_open_ports[ip]:
                    is_open, _ = await probe_port(ip, port, semaphore, timeout=timeout)
                    if is_open:
                        live_open_ports[ip].add(port)
                probes_completed += 1
                if total_stage2_probes > 0:
                    pct = 30 + int((probes_completed / total_stage2_probes) * 60)
                    self._jobs[job_id].progress = min(pct, 90)

            if live_hosts:
                stage2_tasks = [
                    _scan_host_port(ip, port)
                    for ip in sorted(live_hosts)
                    for port in target_ports
                ]
                await asyncio.gather(*stage2_tasks, return_exceptions=True)

            # Stage 3: Resolve hostnames and format results (90% -> 100% progress)
            self._jobs[job_id].progress = 92
            devices: List[DeviceResult] = []

            for ip in sorted(live_hosts):
                open_ports_list = sorted(list(live_open_ports[ip]))
                # Include device if it has open ports or responded
                if open_ports_list:
                    hostname = await resolve_hostname(ip)
                    ports_models = [
                        OpenPort(port=p, service=guess_service_name(p))
                        for p in open_ports_list
                    ]
                    devices.append(
                        DeviceResult(
                            ip=ip,
                            hostname=hostname,
                            open_ports=ports_models,
                        )
                    )

            self._jobs[job_id].devices = devices
            self._jobs[job_id].progress = 100
            self._jobs[job_id].status = "completed"

        except Exception as exc:
            logger.error("Local scan job %s failed: %s", job_id, exc)
            self._jobs[job_id].status = "failed"
            self._jobs[job_id].error = str(exc)

    def start_scan(self, subnet_network: ipaddress.IPv4Network, port_profile: str) -> str:
        """Create a local scan job, enqueue background task, and return job_id."""
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = LocalScanStatusResponse(
            job_id=job_id,
            status="running",
            progress=0,
            devices=[],
        )
        asyncio.create_task(self._execute_scan(job_id, subnet_network, port_profile))
        return job_id


# Global service instance
local_scan_service = LocalScanService()
