# PortHole 98 — Implementation Plan

> **PortHole 98**: A Python FastAPI network diagnostic dashboard styled like a classic Windows 95/98 desktop application. Shows open local network ports, checks public IP reachability, and measures TCP connect latency from 5 continents using check-host.net.

---

## Architecture Overview
- **Backend**: Python 3.11+, FastAPI, `httpx` (async client), Pydantic v2 schemas, `uvicorn`.
- **Services**:
  - `network_info.py`: Public IPv4/IPv6 discovery via ipify, local private subnet detection (/24), router WAN IP via UPnP IGD (`miniupnpc` fallback to null / manual `wan_ip` query parameter), CGNAT classification logic.
  - `checkhost.py`: Integration with check-host.net, continental node distribution (deriving continent from country codes when region tags are absent), defensive polling, stats calculation, 45s in-memory caching.
  - `local_scan.py`: Two-stage scanning: (1) rapid host-discovery on /24 subnet, (2) high-concurrency `asyncio` TCP connect port scan on live hosts only (`asyncio.Semaphore(200)`, 0.5s timeout). Background job model with `job_id` and progress polling. Reverse DNS hostname lookup and service resolution via `socket.getservbyport`.
  - `safety.py`: Enforces RFC1918 private subnets capped at /24 for local scan, restricts public check targets strictly to detected public IP, in-memory per-client rate limiting (5 req/min applied strictly to POST trigger endpoints, exempting GET polling), no persistence of scan data.
  - `stats.py`: Defensive calculation of latency statistics (median, min, max, failed count).
- **Frontend**: Plain HTML5, CSS3, and JavaScript (ES6+) in `web/` with zero frameworks, zero external CDN dependencies, and zero external image files. Pixel-perfect Windows 95/98 aesthetics (teal `#008080` desktop, 3D raised/sunken beveled borders, navy title bar gradient, MS Sans Serif typography, taskbar with working clock, tabbed dialogs, modal message boxes, draggable window).
- **Desktop Wrapper**: `desktop.py` running background uvicorn server on loopback `127.0.0.1` with a random free port and `pywebview` window (900x680, min 640x480). Packaging via PyInstaller with `build/build_exe.bat`.

---

## Milestones

### M1: Network Information (`network_info`)
- [x] Initialize project configuration files (`requirements.txt`, `.env.example`).
- [x] Implement `app/config.py` with environment configuration and resource path resolution (for both source and PyInstaller bundle).
- [x] Implement `app/models.py` with Pydantic schemas: `NetworkInfoResponse` (`public_ipv4`, `public_ipv6`, `router_wan_ip`, `local_subnet`, `cgnat`, `reason`).
- [x] Implement `app/services/network_info.py`:
  - [x] Async fetch of public IPv4 from `https://api.ipify.org?format=json`.
  - [x] Async fetch of public IPv6 from `https://api64.ipify.org?format=json` (return `null` on failure/unsupported network).
  - [x] UPnP IGD router WAN IP retrieval using `miniupnpc` with safe exception handling (return `null` if library missing or discovery fails).
  - [x] Detect active local IPv4 interface and compute private `/24` subnet CIDR (e.g. `192.168.1.0/24`) to prefill in Local Scan tab.
  - [x] CGNAT detection function: accepts optional manual `wan_ip`. Return `cgnat=True` and clear explanatory reason if WAN IP differs from public IP, or WAN IP falls into `100.64.0.0/10` (RFC 6598), or WAN IP is in RFC 1918 private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`). Return `cgnat=False` if WAN IP matches public IP and is publicly routable.
- [x] Create `app/main.py` and register `GET /api/network` endpoint accepting optional `wan_ip` query parameter.
- [x] Verify endpoint locally with a direct invocation script or pytest.
- **Done when**: `GET /api/network` returns HTTP 200 with `{ public_ipv4, public_ipv6, router_wan_ip, local_subnet, cgnat, reason }`, accepts optional `wan_ip` query parameter, gracefully handles missing miniupnpc or UPnP timeout without crashing, and accurately identifies CGNAT according to IP classification rules. (COMPLETED)

---

### M2: check-host.net Integration & Latency Statistics (`checkhost`)
- [x] Implement `app/utils/stats.py`:
  - [x] Calculate `median`, `min`, `max`, and `failed` count from an array of numeric latency samples defensively.
- [x] Implement `app/services/safety.py`:
  - [x] In-memory sliding-window/token-bucket rate limiter: 5 requests per minute per client IP, strictly applied to POST trigger endpoints (exempting polling GET endpoints).
  - [x] Public check target validator: enforce that target IP must strictly match the detected public IP from `network_info`, rejecting arbitrary hostnames or IP addresses.
  - [x] Scan persistence rule: guarantee scan and check results are kept in memory only and not saved to disk or database.
- [x] Implement `app/services/checkhost.py`:
  - [x] Ensure `Accept: application/json` header is sent on every HTTP request to check-host.net.
  - [x] Fetch node list from `https://check-host.net/nodes/hosts`. If node list has no region tags, derive continent/region from each node's 2-letter country code (Europe, North America, Asia, South America, Oceania) and select 1 node per region (falling back to `max_nodes=5` if mapping unavailable).
  - [x] Initiate check via `GET https://check-host.net/check-tcp?host=<public_ip>:<port>&node=<id>...`.
  - [x] Poll `GET https://check-host.net/check-result/<request_id>` every 1.5s for up to 15s; interpret `null` node values as pending.
  - [x] Defensively parse each node's response: handle success `[time, address]` / `{time, address}`, error strings (e.g. timeout, connection refused), and categorize unexpected payloads as `"unknown"` without raising uncaught exceptions.
  - [x] Multi-run coordinator: execute check `runs` times (default 3, max 5) with defensive delays between runs.
  - [x] Aggregate per-location metrics (status, median latency, min latency, max latency, failed runs) using `app/utils/stats.py`.
  - [x] In-memory 45-second cache for check results based on port and runs.
  - [x] Background job manager with unique `job_id` tracking status (`pending`, `running`, `completed`, `failed`).
- [x] Register endpoints in `app/main.py`:
  - [x] `POST /api/check/public` -> `{ "job_id": str }` (rate limited to 5/min)
  - [x] `GET /api/check/public/{job_id}` -> `{ "job_id": str, "status": str, "results": list, "error": str | null }` (not rate limited)
  - [x] `GET /api/nodes` -> list of selected check-host nodes in use.
- [x] Verify node selection, request initiation, defensive parsing, polling, and stats calculation.
- **Done when**: `POST /api/check/public` returns a `job_id` for background execution against the verified public IP, `GET /api/check/public/{job_id}` reports progress and returns defensive aggregated stats across 5 continents, `GET /api/nodes` returns the active node list, and results are cached for 45s. (COMPLETED)

---

### M3: Local Network Scanner (`local_scan`)
- [x] Update `app/services/safety.py`:
  - [x] Validate subnet input: strictly permit only RFC 1918 private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) and cap subnet size at `/24` (prefix length >= 24, e.g. /24 to /32). Reject larger subnets, public subnets, loopback, multicast, or invalid CIDRs with HTTP 400.
- [x] Implement `app/services/local_scan.py`:
  - [x] Define port profiles: `"common"` (21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1433, 3306, 3389, 5432, 8080, 8443, 25565) and `"top1024"` (ports 1 to 1024).
  - [x] Stage 1: Host discovery on `/24` subnet — rapid probe to identify responsive/live IP addresses.
  - [x] Stage 2: Port scanning only on live hosts using concurrent asynchronous TCP connect scan (`asyncio.Semaphore(200)`, `0.5s` connection timeout).
  - [x] Asynchronous hostname reverse lookup (`socket.gethostbyaddr`) with timeout and graceful fallback to IP address string if unresolvable.
  - [x] Service name guessing using `socket.getservbyport(port, "tcp")` with fallback to known dictionary (e.g. 25565 -> "minecraft", 8080 -> "http-alt") or `"unknown"`.
  - [x] Background job manager with `job_id`, status (`pending`, `running`, `completed`, `failed`), and progress percentage.
  - [x] Aggregate open ports by host IP: `[{ "ip": str, "hostname": str | null, "open_ports": [{ "port": int, "service": str }] }]`.
- [x] Register endpoints in `app/main.py`:
  - [x] `POST /api/scan/local` `{ "subnet": str, "ports": "common" | "top1024" }` -> `{ "job_id": str }` (rate limited to 5/min)
  - [x] `GET /api/scan/local/{job_id}` -> `{ "job_id": str, "status": str, "progress": int, "devices": list, "error": str | null }` (not rate limited)
- [x] Verify scanning logic, rate limiting, and subnet rejection.
- **Done when**: `POST /api/scan/local` initiates a background two-stage scan (host discovery then port scan with semaphore=200, timeout=0.5s) on a private /24 subnet, `GET /api/scan/local/{job_id}` returns progress and discovered devices, and non-private or >/24 subnets are rejected with HTTP 400. (COMPLETED)

---

### M4: Retro Windows 95/98 Frontend (`web/`)
- [x] Create `web/index.html`:
  - [x] Classic Windows 95/98 UI markup:
    - [x] Desktop container (`#008080` background).
    - [x] Centered draggable window with 3D beveled borders.
    - [x] Title bar (`linear-gradient(90deg, #000080, #1084d0)`), bold white title, icon glyph, minimize, maximize, close buttons.
    - [x] Menu bar: File (`Run all checks`, `Exit`), View (`Refresh`), Help (`About PortHole 98`).
    - [x] Tab control with 3 tabs: **Network**, **Local Scan**, **Public Check**.
    - [x] Tab 1 (Network): Public IPv4, IPv6, Router WAN IP (with manual override input if UPnP is unavailable), CGNAT indicator and explanation, IPv6 status, etched groupboxes.
    - [x] Tab 2 (Local Scan): Subnet input box (prefilled with detected `local_subnet`), ports dropdown (`common` / `top1024`), `Scan` button, list view table (IP, Hostname, Open Ports), permission note.
    - [x] Tab 3 (Public Check): Port input box, runs dropdown (`1` to `5`, default `3`), `Check` button, segmented blue-block progress bar, sortable list view table (Location, Status, Median ms, Min, Max, Failed) with raised headers.
    - [x] Sunken status bar at bottom with multiple status panels ("Ready", active info, system status).
    - [x] Taskbar at screen bottom: Start button (raised bevel, pressed state, start menu popover), active task button, system tray with sunken 12-hour/24-hour live clock.
    - [x] Modal dialog components: Error message box, Warning message box, CGNAT notice box, and About dialog with network permission notice.
- [x] Create `web/style.css`:
  - [x] Strict Windows 95/98 color palette: Face `#c0c0c0`, highlight `#ffffff`, light shadow `#dfdfdf`, dark shadow `#808080`, black `#000000`, teal `#008080`, navy `#000080`, bright blue `#1084d0`.
  - [x] Authentic 3D box-shadow bevels (raised 2px, sunken 2px, etched 2px groupboxes).
  - [x] Zero border-radius and zero modern drop shadows.
  - [x] Typography: `"MS Sans Serif", Tahoma, Arial, sans-serif` at 11px for UI elements; `"Courier New", monospace` for IP addresses and raw results.
  - [x] Interactive button states: pressed state with sunken border and 1px text shift (`transform: translate(1px, 1px)`); dotted focus rectangle (`outline: 1px dotted #000`).
  - [x] Hourglass cursor (`cursor: wait`) when operations are active.
  - [x] Classic segmented progress bar styling (repeated blue blocks).
  - [x] Responsive rules: minimum width ~640px; fills viewport cleanly on smaller viewports.
- [x] Create `web/app.js`:
  - [x] Window drag-and-drop logic via title bar with boundary containment.
  - [x] Tab switching logic.
  - [x] Taskbar clock updater (updates every second).
  - [x] Start menu toggle and menu item handlers (Run all checks, Refresh, Exit, About).
  - [x] Modal dialog controller (show/hide with backdrop, classic title bar, icon, message, and OK button).
  - [x] Network tab handler: load `GET /api/network`, populate fields, prefill local subnet in Local Scan tab, handle manual WAN IP override, trigger CGNAT alert modal if detected.
  - [x] Local scan tab handler: submit `POST /api/scan/local`, poll `GET /api/scan/local/{job_id}`, update progress, render open ports list view, show hourglass cursor and status bar updates.
  - [x] Public check tab handler: submit `POST /api/check/public`, poll `GET /api/check/public/{job_id}`, animate segmented progress bar, populate table.
  - [x] Column header sorting for Public Check table (sort by location, status, median, min, max, failed on click).
- [x] Mount `web/` static files in `app/main.py`.
- [x] Verify UI layout, responsiveness, animations, drag functionality, sorting, and API integration.
- **Done when**: Opening the browser at `http://127.0.0.1:8000/` displays a faithful Windows 95/98 desktop experience where all tabs, buttons, modals, sorting, and drag-and-drop work smoothly without external assets or libraries. (COMPLETED)

---

### M5: Automated Test Suite (`tests/`)
- [x] Implement `tests/test_cgnat.py`:
  - [x] Unit tests for CGNAT detection logic (matching public IP, mismatched WAN IP, `100.64.0.0/10` shared address space, RFC 1918 private WAN IP, IPv6 present/absent).
- [x] Implement `tests/test_checkhost.py`:
  - [x] Unit tests for check-host defensive parser: valid latency arrays, string timeouts, connection errors, `null` in-flight results, and malformed objects without crashing.
  - [x] Unit tests for `stats.py` calculations (median, min, max, failed runs with edge cases like all failures or single success).
- [x] Implement `tests/test_safety.py`:
  - [x] Subnet validator tests: accepts `10.0.0.0/24`, `172.16.1.0/24`, `192.168.1.0/24`; rejects `8.8.8.0/24`, `1.1.1.1`, subnets larger than /24 (e.g. `10.0.0.0/16`), loopback, invalid CIDR strings.
  - [x] Public check target validator tests: prevents user from overriding or targeting arbitrary hosts.
  - [x] Rate limiter tests: applies strictly to POST trigger endpoints (allows up to 5 requests per minute, rejects the 6th with HTTP 429), does not block polling GET endpoints.
- [x] Implement `tests/test_api.py`:
  - [x] FastAPI endpoint integration tests (`GET /api/network`, `POST /api/scan/local`, `GET /api/scan/local/{job_id}`, `POST /api/check/public`, `GET /api/check/public/{job_id}`, `GET /api/nodes`).
- [x] Run pytest suite and ensure all tests pass cleanly.
- **Done when**: `pytest` executes and all test cases across CGNAT, check-host parsing, safety policies, rate limiting, and API endpoints pass with 100% success rate. (COMPLETED)

---

### M6: Documentation & Environment Setup
- [x] Create `README.md`:
  - [x] Project overview and features.
  - [x] Installation instructions (Python 3.11+, virtual environment, requirements).
  - [x] Development execution instructions (`uvicorn app.main:app --reload`).
  - [x] Desktop app instructions (`python desktop.py`).
  - [x] Detailed API endpoint documentation with sample requests and responses.
  - [x] Check-host.net integration details, rate limiting policies, and caching explanation.
  - [x] Legal disclaimer / network testing permissions note.
  - [x] Screenshot placeholder.
- [x] Verify `.env.example` with environment variable definitions.
- **Done when**: `README.md` and `.env.example` are comprehensive, accurate, and completely aligned with the project specification. (COMPLETED)

---

### M7: Desktop Launcher & Executable Build (`desktop.py`, `build/`)
- [x] Implement `desktop.py`:
  - [x] Start FastAPI via uvicorn in a daemon background thread bound strictly to `127.0.0.1` on a dynamically assigned free port.
  - [x] Probe loop until server responds at `http://127.0.0.1:{port}/`.
  - [x] Launch `pywebview` window: title "PortHole 98", dimensions 900x680, minimum size 640x480.
  - [x] Catch missing WebView2 runtime on Windows and present an informative error dialog with Microsoft download link.
  - [x] Gracefully shut down background uvicorn server upon window close.
- [x] Ensure resource-path helper in `app/config.py` correctly resolves `web/` assets from `sys._MEIPASS` when running in a PyInstaller bundle.
- [x] Create retro Windows `.ico` icon in `build/icon.ico`.
- [x] Create `build/build_exe.bat` for PyInstaller packaging:
  - [x] Command: `pyinstaller --onefile --windowed --name PortHole98 --icon build\icon.ico --add-data "web;web" desktop.py`.
- [x] Test dual execution modes: `uvicorn app.main:app --reload` and `python desktop.py`.
- **Done when**: The application runs successfully both as a standard browser app via uvicorn and as a native desktop application via `python desktop.py`, with `build/build_exe.bat` configured for PyInstaller bundling. (COMPLETED)
