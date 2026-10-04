"""Integration with check-host.net for global port reachability and latency checks."""

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.models import CheckNodeInfo, LocationLatencyResult, PublicCheckStatusResponse
from app.utils.stats import calculate_latency_stats

logger = logging.getLogger(__name__)

# Headers required by check-host.net
CHECKHOST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PortHole98/1.0 (Windows 98; Netscape/4.0)",
}

# Mapping of country codes to continents
COUNTRY_TO_REGION = {
    # Europe
    "at": "Europe", "be": "Europe", "bg": "Europe", "ch": "Europe", "cy": "Europe",
    "cz": "Europe", "de": "Europe", "dk": "Europe", "es": "Europe", "fi": "Europe",
    "fr": "Europe", "gb": "Europe", "gr": "Europe", "hr": "Europe", "hu": "Europe",
    "ie": "Europe", "is": "Europe", "it": "Europe", "lt": "Europe", "lu": "Europe",
    "lv": "Europe", "md": "Europe", "nl": "Europe", "no": "Europe", "pl": "Europe",
    "pt": "Europe", "ro": "Europe", "rs": "Europe", "ru": "Europe", "se": "Europe",
    "si": "Europe", "sk": "Europe", "ua": "Europe",
    # North America
    "us": "North America", "ca": "North America", "mx": "North America",
    # Asia
    "cn": "Asia", "hk": "Asia", "id": "Asia", "il": "Asia", "in": "Asia",
    "ir": "Asia", "jp": "Asia", "kr": "Asia", "kz": "Asia", "my": "Asia",
    "ph": "Asia", "sg": "Asia", "th": "Asia", "tr": "Asia", "tw": "Asia", "vn": "Asia",
    # South America
    "ar": "South America", "br": "South America", "cl": "South America",
    "co": "South America", "pe": "South America",
    # Oceania
    "au": "Oceania", "nz": "Oceania",
}

TARGET_REGIONS = ("Europe", "North America", "Asia", "South America", "Oceania")

# Fallback nodes if live discovery is unreachable
FALLBACK_NODES = [
    CheckNodeInfo(id="de1.node.check-host.net", name="Germany (Frankfurt)", country="Germany", region="Europe"),
    CheckNodeInfo(id="us1.node.check-host.net", name="USA (New York)", country="USA", region="North America"),
    CheckNodeInfo(id="jp1.node.check-host.net", name="Japan (Tokyo)", country="Japan", region="Asia"),
    CheckNodeInfo(id="br1.node.check-host.net", name="Brazil (Sao Paulo)", country="Brazil", region="South America"),
    CheckNodeInfo(id="au1.node.check-host.net", name="Australia (Sydney)", country="Australia", region="Oceania"),
]


class CheckHostService:
    """Manages check-host.net communication, regional node selection, job tracking, and caching."""

    def __init__(self) -> None:
        self._cached_nodes: Optional[List[CheckNodeInfo]] = None
        self._nodes_last_fetched: float = 0.0
        self._jobs: Dict[str, PublicCheckStatusResponse] = {}
        # In-memory 45s cache: key -> (timestamp, list of LocationLatencyResult)
        self._results_cache: Dict[str, Tuple[float, List[LocationLatencyResult]]] = {}

    async def get_nodes(self, client: Optional[httpx.AsyncClient] = None) -> List[CheckNodeInfo]:
        """Fetch and return 5 geographic nodes across 5 continents."""
        now = time.monotonic()
        if self._cached_nodes and (now - self._nodes_last_fetched < 3600.0):
            return self._cached_nodes

        should_close = False
        if client is None:
            client = httpx.AsyncClient(headers=CHECKHOST_HEADERS, timeout=8.0)
            should_close = True

        try:
            resp = await client.get("https://check-host.net/nodes/hosts")
            if resp.status_code == 200:
                data = resp.json()
                raw_nodes = data.get("nodes", {})
                selected: Dict[str, CheckNodeInfo] = {}

                for node_id, node_data in raw_nodes.items():
                    loc = node_data.get("location", [])
                    if loc and len(loc) >= 2:
                        country_code = str(loc[0]).lower()
                        country_name = str(loc[1])
                        city_name = str(loc[2]) if len(loc) >= 3 else ""
                        region = COUNTRY_TO_REGION.get(country_code, "Other")

                        if region in TARGET_REGIONS and region not in selected:
                            display_name = f"{country_name} ({city_name})" if city_name else country_name
                            selected[region] = CheckNodeInfo(
                                id=node_id,
                                name=display_name,
                                country=country_name,
                                region=region,
                            )

                # If all 5 target regions were found, use them
                if len(selected) == len(TARGET_REGIONS):
                    self._cached_nodes = [selected[r] for r in TARGET_REGIONS]
                    self._nodes_last_fetched = now
                    return self._cached_nodes

                # If some regions were missing, pick top 5 distinct nodes
                if len(selected) >= 3:
                    self._cached_nodes = list(selected.values())[:5]
                    self._nodes_last_fetched = now
                    return self._cached_nodes
        except Exception as exc:
            logger.warning("Failed to fetch check-host.net nodes: %s", exc)
        finally:
            if should_close:
                await client.aclose()

        self._cached_nodes = list(FALLBACK_NODES)
        self._nodes_last_fetched = now
        return self._cached_nodes

    def parse_node_result(self, raw_result: Any) -> Tuple[str, Optional[float]]:
        """
        Defensively parse a single node result from check-host.net.

        Returns:
            (status_string, latency_ms_or_none)
        """
        if raw_result is None:
            return "pending", None

        # Standard check-host result is a list: [{'address': '...', 'time': 0.042}] or [{'error': '...'}]
        if isinstance(raw_result, list):
            if not raw_result:
                return "unknown", None

            first_item = raw_result[0]
            if isinstance(first_item, dict):
                # Success case: {'address': '...', 'time': seconds}
                if "time" in first_item:
                    try:
                        seconds = float(first_item["time"])
                        latency_ms = round(seconds * 1000.0, 2)
                        return "Open", latency_ms
                    except (ValueError, TypeError):
                        pass

                # Error case: {'error': 'Connection timed out'}
                if "error" in first_item:
                    return str(first_item["error"]), None

            if isinstance(first_item, str):
                return first_item, None

        # Dict shape fallback
        if isinstance(raw_result, dict):
            if "time" in raw_result:
                try:
                    seconds = float(raw_result["time"])
                    return "Open", round(seconds * 1000.0, 2)
                except (ValueError, TypeError):
                    pass
            if "error" in raw_result:
                return str(raw_result["error"]), None

        return "unknown", None

    async def _execute_single_run(
        self,
        client: httpx.AsyncClient,
        public_ip: str,
        port: int,
        nodes: List[CheckNodeInfo],
    ) -> Dict[str, Tuple[str, Optional[float]]]:
        """Initiate one check and poll check-host.net until nodes finish or 15s timeout."""
        params: List[Tuple[str, str]] = [("host", f"{public_ip}:{port}")]
        for n in nodes:
            params.append(("node", n.id))

        resp = await client.get("https://check-host.net/check-tcp", params=params)
        if resp.status_code != 200:
            raise RuntimeError(f"check-host.net check-tcp returned HTTP {resp.status_code}")

        data = resp.json()
        if not data.get("ok"):
            err_msg = data.get("error", "check-host request failed")
            if err_msg == "limit_exceeded":
                raise RuntimeError("check-host.net rate limit exceeded. Please wait a moment before trying again.")
            raise RuntimeError(f"check-host error: {err_msg}")

        request_id = data.get("request_id")
        if not request_id:
            raise RuntimeError("check-host did not return a request_id")

        run_results: Dict[str, Tuple[str, Optional[float]]] = {}
        pending_nodes = {n.id for n in nodes}

        # Poll check-result every 1.5s up to 15s
        max_polls = 10  # 10 * 1.5s = 15s
        for _ in range(max_polls):
            await asyncio.sleep(1.5)
            poll_resp = await client.get(f"https://check-host.net/check-result/{request_id}")
            if poll_resp.status_code != 200:
                continue

            poll_data = poll_resp.json()
            if not isinstance(poll_data, dict):
                continue

            for node_id in list(pending_nodes):
                if node_id in poll_data:
                    raw_val = poll_data[node_id]
                    if raw_val is not None:
                        status, latency = self.parse_node_result(raw_val)
                        run_results[node_id] = (status, latency)
                        pending_nodes.remove(node_id)

            if not pending_nodes:
                break

        # Any remaining pending nodes are marked as timed out
        for node_id in pending_nodes:
            run_results[node_id] = ("Timeout", None)

        return run_results

    async def _run_check_job(
        self,
        job_id: str,
        public_ip: str,
        port: int,
        runs: int,
    ) -> None:
        """Background worker that executes `runs` iterations, calculates statistics, and caches."""
        cache_key = f"{public_ip}:{port}:{runs}"
        now = time.monotonic()

        # Check in-memory 45s cache
        if cache_key in self._results_cache:
            cache_time, cached_results = self._results_cache[cache_key]
            if now - cache_time < 45.0:
                self._jobs[job_id] = PublicCheckStatusResponse(
                    job_id=job_id,
                    status="completed",
                    results=cached_results,
                )
                return

        nodes = await self.get_nodes()
        # Per-node accumulator: node_id -> {"samples": [latencies], "failed": count, "last_status": str}
        node_stats: Dict[str, Dict[str, Any]] = {
            n.id: {"samples": [], "failed": 0, "last_status": "Closed"}
            for n in nodes
        }

        async with httpx.AsyncClient(headers=CHECKHOST_HEADERS, timeout=12.0) as client:
            try:
                for run_idx in range(runs):
                    if run_idx > 0:
                        await asyncio.sleep(1.2)  # Defensive delay between runs to respect check-host

                    single_run = await self._execute_single_run(client, public_ip, port, nodes)

                    for node_id, (status, latency) in single_run.items():
                        if node_id in node_stats:
                            if latency is not None:
                                node_stats[node_id]["samples"].append(latency)
                                node_stats[node_id]["last_status"] = "Open"
                            else:
                                node_stats[node_id]["failed"] += 1
                                node_stats[node_id]["last_status"] = status

                # Compute final location statistics
                final_results: List[LocationLatencyResult] = []
                for n in nodes:
                    stats = node_stats[n.id]
                    samples: List[float] = stats["samples"]
                    failed: int = stats["failed"]
                    last_status: str = stats["last_status"]

                    median, min_val, max_val, failed_count = calculate_latency_stats(samples, failed)

                    if samples and failed == 0:
                        overall_status = "Open"
                    elif samples and failed > 0:
                        overall_status = f"Open ({len(samples)}/{len(samples) + failed})"
                    else:
                        overall_status = last_status if last_status != "pending" else "Closed / Filtered"

                    final_results.append(
                        LocationLatencyResult(
                            location=n.name,
                            country=n.country,
                            region=n.region,
                            status=overall_status,
                            median=median,
                            min=min_val,
                            max=max_val,
                            failed=failed_count,
                        )
                    )

                # Cache results for 45s
                self._results_cache[cache_key] = (time.monotonic(), final_results)

                self._jobs[job_id] = PublicCheckStatusResponse(
                    job_id=job_id,
                    status="completed",
                    results=final_results,
                )
            except Exception as exc:
                logger.error("Public check job %s failed: %s", job_id, exc)
                self._jobs[job_id] = PublicCheckStatusResponse(
                    job_id=job_id,
                    status="failed",
                    results=[],
                    error=str(exc),
                )

    def start_check(self, public_ip: str, port: int, runs: int = 3) -> str:
        """Create and dispatch a background public check job, returning its job_id."""
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = PublicCheckStatusResponse(
            job_id=job_id,
            status="running",
            results=[],
        )
        asyncio.create_task(self._run_check_job(job_id, public_ip, port, runs))
        return job_id

    def get_job_status(self, job_id: str) -> Optional[PublicCheckStatusResponse]:
        """Retrieve the status and results of a check job by ID."""
        return self._jobs.get(job_id)


# Global service instance
checkhost_service = CheckHostService()
