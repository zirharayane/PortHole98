"""Integration tests for PortHole 98 FastAPI endpoints and static web routing."""

import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.safety import rate_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear in-memory rate limiter state before each test."""
    rate_limiter._requests.clear()


def test_get_network_info_default():
    """GET /api/network returns network details and CGNAT classification."""
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/network")
            assert resp.status_code == 200
            data = resp.json()
            assert "public_ipv4" in data
            assert "public_ipv6" in data
            assert "router_wan_ip" in data
            assert "local_subnet" in data
            assert "cgnat" in data
            assert "reason" in data
    asyncio.run(_run())


def test_get_network_info_manual_wan_override():
    """GET /api/network?wan_ip=... applies manual override and computes CGNAT."""
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/network?wan_ip=100.64.10.20")
            assert resp.status_code == 200
            data = resp.json()
            assert data["router_wan_ip"] == "100.64.10.20"
            assert data["cgnat"] is True
            assert "100.64.0.0/10" in data["reason"]
    asyncio.run(_run())


def test_get_nodes():
    """GET /api/nodes returns 5 nodes covering global regions."""
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/nodes")
            assert resp.status_code == 200
            nodes = resp.json()
            assert isinstance(nodes, list)
            assert len(nodes) == 5
            for node in nodes:
                assert "id" in node
                assert "name" in node
                assert "country" in node
                assert "region" in node
    asyncio.run(_run())


def test_local_scan_flow():
    """POST /api/scan/local starts job and GET /api/scan/local/{job_id} tracks progress."""
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Start scan on small test private subnet
            resp = await client.post("/api/scan/local", json={"subnet": "192.168.1.0/30", "ports": "common"})
            assert resp.status_code == 200
            data = resp.json()
            assert "job_id" in data
            job_id = data["job_id"]

            # Poll status
            status_resp = await client.get(f"/api/scan/local/{job_id}")
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            assert status_data["job_id"] == job_id
            assert status_data["status"] in ("running", "completed")
    asyncio.run(_run())


def test_public_check_flow():
    """POST /api/check/public starts check and GET /api/check/public/{job_id} polls status."""
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/check/public", json={"port": 80, "runs": 1})
            assert resp.status_code == 200
            data = resp.json()
            assert "job_id" in data
            job_id = data["job_id"]

            status_resp = await client.get(f"/api/check/public/{job_id}")
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            assert status_data["job_id"] == job_id
            assert status_data["status"] in ("running", "completed")
    asyncio.run(_run())


def test_static_files_serving():
    """Verify root / serves HTML dashboard and static assets."""
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code == 200
            assert "PortHole 98" in resp.text

            css_resp = await client.get("/style.css")
            assert css_resp.status_code == 200
            assert "--win-desktop" in css_resp.text

            js_resp = await client.get("/app.js")
            assert js_resp.status_code == 200
            assert "PortHole 98" in js_resp.text
    asyncio.run(_run())
