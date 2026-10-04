<div align="center">

# 🕳️ PortHole 98

### Is your port *really* open to the world? Find out from 5 continents, in a Windows 98 window.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)
![UI](https://img.shields.io/badge/UI-Windows%2095%2F98-008080)
![License](https://img.shields.io/badge/License-MIT-green)

**Made by Rayane Zirha · RZ™**

<!-- Replace with a real screenshot or a short GIF of the app -->
<img src="docs/screenshot.png" alt="PortHole 98 screenshot" width="720">

</div>

---

## Why PortHole 98?

You set up a port forward. Your friends still can't connect. Is it your firewall? Your router? Your ISP? Or are you stuck behind **CGNAT** and no setting will ever work?

PortHole 98 answers that in one window:

- 🔎 **Scans your local network** and shows every device and its open ports.
- 🌍 **Tests your public IP from 5 continents** and reports the TCP connect time per location.
- 🧱 **Detects CGNAT** by comparing your router's WAN IP with your public IP, so you know if public checks can *ever* succeed.
- 📡 **Checks IPv6** availability, because on some lines it's the way around CGNAT.
- 🖥️ **Looks like it's 1998.** Bevelled buttons, navy title bar, message boxes and all. Zero images, zero frameworks.

It started as a real problem: friends lagging out of a home-hosted Minecraft server. The tool I wished existed became this project.

---

## Features

| | |
|---|---|
| **Network tab** | Public IPv4/IPv6, router WAN IP (UPnP, or enter it manually), CGNAT verdict with an explanation |
| **Local Scan tab** | Async TCP scanner for your own subnet, hostname lookup, service names, common or top-1024 port profiles |
| **Public Check tab** | Latency from 5 regions via [check-host.net](https://check-host.net), repeated runs, median / min / max / failed counts, sortable table |
| **Desktop app** | Runs in its own native window and packages into a single `PortHole98.exe` |
| **Web mode** | Same app in your browser for development |
| **Safety built in** | Private-range scans only, public checks only ever test *your own* IP, rate limits, nothing saved to disk |

---

## Quick start

```bash
git clone https://github.com/<your-username>/porthole98.git
cd porthole98
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

**Run it as a desktop app**

```bash
python desktop.py
```

**Run it in the browser (development)**

```bash
uvicorn app.main:app --reload
# open http://127.0.0.1:8000
```

**Build a standalone .exe**

```bash
build\build_exe.bat
# result: dist\PortHole98.exe
```

> Windows SmartScreen or antivirus may warn about the .exe because it is unsigned and built with PyInstaller. That is a common false alarm for network tools. The full source is in this repo.

---

## How it works

```
┌──────────────────────────────┐
│  Retro GUI (HTML/CSS/JS)     │  no frameworks, no images
└──────────────┬───────────────┘
               │ localhost only (127.0.0.1)
┌──────────────▼───────────────┐
│  FastAPI backend (async)     │
│  ├─ network_info  → ipify, UPnP, CGNAT logic
│  ├─ local_scan    → asyncio TCP scanner
│  ├─ checkhost     → check-host.net client + stats
│  └─ safety        → private ranges, own-IP only, rate limits
└──────────────────────────────┘
```

**CGNAT detection:** your router's WAN IP is compared with the public IP the internet sees. CGNAT is flagged if they differ, or if the WAN IP is in `100.64.0.0/10` or a private range. If the router's address can't be read, the app says **UNKNOWN** instead of guessing.

**Latency numbers:** a single TCP handshake can be an outlier, so each location is checked several times and the app reports the median.

---

## API

| Method | Endpoint | What it does |
|---|---|---|
| GET | `/api/network` | Public IPs, router WAN IP, CGNAT verdict, detected local subnet |
| POST | `/api/scan/local` | Scans a private subnet for open ports |
| POST | `/api/check/public` | Starts a public reachability check for a port on your own public IP |
| GET | `/api/check/public/{job_id}` | Progress and results of a check |
| GET | `/api/nodes` | The check-host.net locations in use |

---

## Safety and ethics

PortHole 98 is for **your own network**.

- Local scans are only accepted for private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
- The public check only tests the IP the app detects for *you*, never a host someone types in.
- Scan and check endpoints are rate limited.
- Results live in memory only and are never written to disk.
- The server binds to `127.0.0.1`, so nobody else on your network can use it.

Only scan networks you own or have explicit permission to test.

---

## Roadmap

- [ ] Scan history and export (CSV/JSON)
- [ ] New-device alerts on your LAN
- [ ] UDP port checks
- [ ] Signed installer
- [ ] Light "classic themes" (Windows 95 teal, 98 standard, high contrast)

---

## Credits

- Public multi-location checks by [check-host.net](https://check-host.net)
- Public IP lookup by [ipify](https://www.ipify.org)
- Window and Windows 95/98 look inspired by classic Windows interface design. Not affiliated with Microsoft.

---

<div align="center">

**Made by Rayane Zirha · RZ™**

If PortHole 98 helped you debug a port, drop a ⭐

</div>