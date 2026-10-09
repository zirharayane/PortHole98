"""PortHole 98 — Main FastAPI Application."""

import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app.config import settings
from app.models import (
    CheckNodeInfo,
    JobCreatedResponse,
    LocalScanRequest,
    LocalScanStatusResponse,
    NetworkInfoResponse,
    PublicCheckRequest,
    PublicCheckStatusResponse,
)
from app.services.checkhost import checkhost_service
from app.services.local_scan import local_scan_service
from app.services.network_info import (
    classify_cgnat,
    detect_local_subnet,
    get_public_ipv4,
    get_public_ipv6,
    get_router_wan_ip_upnp,
)
from app.services.safety import (
    get_client_ip,
    rate_limiter,
    validate_private_subnet,
)

app = FastAPI(
    title="PortHole 98",
    description="Windows 95/98 styled network diagnostic tool",
    version="1.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/network", response_model=NetworkInfoResponse)
async def get_network_info(
    wan_ip: Optional[str] = Query(None, description="Optional manual router WAN IP override")
) -> NetworkInfoResponse:
    """
    Retrieve public IPv4, IPv6, router WAN IP, local /24 subnet, and CGNAT classification.
    """
    async def _fetch_wan() -> Optional[str]:
        if wan_ip and wan_ip.strip():
            return wan_ip.strip()
        try:
            return await asyncio.wait_for(asyncio.to_thread(get_router_wan_ip_upnp), timeout=1.0)
        except Exception:
            return None

    try:
        ipv4_task = asyncio.create_task(get_public_ipv4())
        ipv6_task = asyncio.create_task(get_public_ipv6())
        wan_task = asyncio.create_task(_fetch_wan())

        public_ipv4, public_ipv6, resolved_wan_ip = await asyncio.wait_for(
            asyncio.gather(ipv4_task, ipv6_task, wan_task),
            timeout=2.5
        )
    except Exception:
        public_ipv4, public_ipv6, resolved_wan_ip = None, None, (wan_ip.strip() if wan_ip else None)

    local_subnet = detect_local_subnet()
    cgnat_detected, reason = classify_cgnat(public_ipv4, resolved_wan_ip)

    return NetworkInfoResponse(
        public_ipv4=public_ipv4,
        public_ipv6=public_ipv6,
        router_wan_ip=resolved_wan_ip,
        local_subnet=local_subnet,
        cgnat=cgnat_detected,
        reason=reason,
    )


@app.get("/api/nodes", response_model=List[CheckNodeInfo])
async def get_check_nodes() -> List[CheckNodeInfo]:
    """Retrieve the 5 geographic check-host.net nodes across 5 continents in use."""
    return await checkhost_service.get_nodes()


@app.post("/api/scan/local", response_model=JobCreatedResponse)
async def start_local_scan(
    request: Request,
    payload: LocalScanRequest,
) -> JobCreatedResponse:
    """
    Initiate a local subnet port scan using two-stage host discovery and TCP connect scanning.
    Rate limited to 5 requests per minute per client IP. Capped at /24 private networks.
    """
    client_ip = get_client_ip(request)
    rate_limiter.check(client_ip)

    # Validate that subnet is private and <= /24
    validated_net = validate_private_subnet(payload.subnet)

    job_id = local_scan_service.start_scan(
        subnet_network=validated_net,
        port_profile=payload.ports,
    )

    return JobCreatedResponse(job_id=job_id)


@app.get("/api/scan/local/{job_id}", response_model=LocalScanStatusResponse)
async def get_local_scan_status(job_id: str) -> LocalScanStatusResponse:
    """
    Poll status, progress, and discovered open ports of a local network scan.
    Not rate limited.
    """
    job = local_scan_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found.")
    return job


@app.post("/api/check/public", response_model=JobCreatedResponse)
async def start_public_check(
    request: Request,
    payload: PublicCheckRequest,
) -> JobCreatedResponse:
    """
    Trigger a global port reachability and latency check against the verified public IPv4.
    Rate limited to 5 requests per minute per client IP.
    """
    client_ip = get_client_ip(request)
    rate_limiter.check(client_ip)

    public_ipv4 = await get_public_ipv4()
    if not public_ipv4:
        raise HTTPException(
            status_code=503,
            detail="Public IPv4 could not be determined. Check internet connectivity."
        )

    job_id = checkhost_service.start_check(
        public_ip=public_ipv4,
        port=payload.port,
        runs=payload.runs,
    )

    return JobCreatedResponse(job_id=job_id)


@app.get("/api/check/public/{job_id}", response_model=PublicCheckStatusResponse)
async def get_public_check_status(job_id: str) -> PublicCheckStatusResponse:
    """
    Poll status and results of a public port reachability check.
    Not rate limited.
    """
    job = checkhost_service.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Check job not found.")
    return job


# Mount static web dashboard (registered after all API routes)
if settings.web_dir.exists():
    app.mount("/", StaticFiles(directory=str(settings.web_dir), html=True), name="web")

