"""Pydantic data models for PortHole 98 API schemas."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class NetworkInfoResponse(BaseModel):
    """Network information discovery and CGNAT classification response."""
    public_ipv4: Optional[str] = Field(None, description="Discovered public IPv4 address")
    public_ipv6: Optional[str] = Field(None, description="Discovered public IPv6 address, if available")
    router_wan_ip: Optional[str] = Field(None, description="Router WAN IP via UPnP IGD or manual entry")
    local_subnet: Optional[str] = Field(None, description="Detected local private subnet CIDR (e.g., 192.168.1.0/24)")
    cgnat: bool = Field(False, description="True if Carrier-Grade NAT is detected")
    reason: str = Field(..., description="Explanation of the CGNAT determination")


class LocalScanRequest(BaseModel):
    """Payload to initiate a local subnet port scan."""
    subnet: str = Field(..., description="Private subnet in CIDR notation (e.g., 192.168.1.0/24)")
    ports: Literal["common", "top1024"] = Field("common", description="Port profile to scan")


class OpenPort(BaseModel):
    """Information about an open port on a network host."""
    port: int
    service: str


class DeviceResult(BaseModel):
    """A discovered device with its open ports."""
    ip: str
    hostname: Optional[str] = None
    open_ports: list[OpenPort] = Field(default_factory=list)


class JobCreatedResponse(BaseModel):
    """Response returned when an asynchronous background job is started."""
    job_id: str


class LocalScanStatusResponse(BaseModel):
    """Status and results of an ongoing or completed local scan job."""
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    progress: int = Field(0, ge=0, le=100)
    devices: list[DeviceResult] = Field(default_factory=list)
    error: Optional[str] = None


class PublicCheckRequest(BaseModel):
    """Payload to check public port reachability and latency across global nodes."""
    port: int = Field(..., ge=1, le=65535, description="Port number to test")
    runs: int = Field(3, ge=1, le=5, description="Number of test iterations (1-5)")


class LocationLatencyResult(BaseModel):
    """Latency statistics for a specific geographic node."""
    location: str
    country: str
    region: str
    status: str
    median: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    failed: int = 0


class PublicCheckStatusResponse(BaseModel):
    """Status and results of an ongoing or completed public port reachability check."""
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    results: list[LocationLatencyResult] = Field(default_factory=list)
    error: Optional[str] = None


class CheckNodeInfo(BaseModel):
    """Information about a check-host.net node."""
    id: str
    name: str
    country: str
    region: str
