# PortHole 98: Research Log

How the idea went from a question ("can an app see my open ports and test them from other countries?") to a working app, including the questions asked, what was found, and what was decided.

Author: Rayane Zirha · RZ™
Date: October 4, 2026

> Personal details such as IP addresses and device names are left out on purpose.

---

## 1. Questions asked, in order, and what came out of them

| # | Question | Answer / finding |
|---|---|---|
| 1 | Can I make an app that shows open ports on my WiFi, whether they're public, and how fast they are from 4-5 locations? | Yes. Three parts: a local scan (TCP connects), a public reachability check from a machine *outside* the network, and latency from several locations (TCP handshake time). It measures latency, not bandwidth. |
| 2 | Can one person build this for free? | Mostly yes. The local scan and dashboard cost nothing. The multi-location part is the only costly bit if you run your own servers (about $4-5/month per VPS). |
| 3 | What about using an existing multi-location checker? | **Decision:** use check-host.net. It runs TCP checks from many countries and has an API, so no servers are needed. Trade-off: third-party dependency and rate limits. |
| 4 | My ISP uses CGNAT. What does that change? | Behind CGNAT, public checks always fail because the router has no real public IP. The app should **detect CGNAT** (router WAN IP vs public IP, plus the `100.64.0.0/10` range). Workarounds: tunnels, IPv6, a public IP from the ISP, or a VPS reverse tunnel. |
| 5 | Does IPv6 work on Orange Morocco fibre? | Web searches found no reliable confirmation either way. **Tested instead** with test-ipv6.com: no IPv6 on this line (0/10). |
| 6 | Am I really behind CGNAT? | Checked the Livebox status page. The WAN IP on the INTERNET (PPPoE) connection matched the public IP, so **no CGNAT**. (The private address on the VOIX connection is the phone service, unrelated.) |
| 7 | Can I actually reach a forwarded port from outside? | Yes. Forwarded TCP 8080 on the Livebox, ran a simple local web server, and checked it on check-host.net. It connected from most locations. A few probes timed out (Cyprus, Iran nodes), and a few showed slow handshakes (retries). |
| 8 | Why do friends lag and time out when joining my Minecraft server? | Investigated causes: missing UDP forward (not relevant for Java, which is TCP only), PPPoE MTU (tested, fine), server load, upload speed, Livebox Anti-DoS limit, plugins, and the route from friends to the ISP. It worked through playit.gg, which points to the direct inbound path. **Root cause not yet confirmed**; the Anti-DoS threshold test was the next step. |
| 9 | Make a clean structure, with APIs, and a prompt to build it. | Produced a folder structure, endpoint design, check-host API usage, safety rules and a build prompt. |
| 10 | Give it a name and a classic Windows look, and make the agent follow a plan. | Name: **PortHole 98**. Windows 95/98 UI spec, plus a "HOW TO WORK" block that forces the agent to write `PLAN.md`, work milestone by milestone, and stop for approval. |
| 11 | I want it as an app, not only a website. | Added a desktop mode (pywebview window + PyInstaller `.exe`). Reason: a hosted website can't scan your home network, so desktop is the real product. |
| 12 | Review the agent's plan. | Found six issues (slow full-port scans, rate limit hitting polling, no manual WAN IP path, no subnet detection, fragile region selection, missing port 25565) and sent corrections. |
| 13 | Review the first screenshots. | Found a false "no CGNAT" badge shown when the WAN IP was unknown, and a stale "check complete" status on startup. Both fixed. Removed the teal desktop and taskbar, added branding, made the window frameless. |
| 14 | What are these open ports on my network? | Router (DNS + admin web), a Windows PC (file sharing ports), and one device with Remote Desktop open that needed identifying. None reachable from the internet. |

---

## 2. Key technical findings

- **TCP handshake time is a good latency proxy**, but single samples are noisy (a retried packet shows up as ~1 second). Use the **median of several runs**.
- **CGNAT vs a real public IP** can be told apart by comparing the router's WAN address to the address the internet sees.
- **A public IP does not guarantee reachability.** The ISP or the router firewall can still filter inbound traffic, so testing from outside is the only proof.
- **Timeouts from a few probes don't mean your port is closed.** They can be routing or filtering on the probe's side, which is why the app shows per-location results.
- **Don't trust a green badge when data is missing.** Unknown must look different from "OK".
- **Safety by design:** the public check may only target the user's own public IP, and local scans only accept private ranges. This stops the tool being used against other people.

---

## 3. How it was built

1. **Research and feasibility** (questions 1-8): explored the problem and tested it on a real home connection.
2. **Specification**: wrote one detailed prompt covering architecture, API design, external API usage, safety rules, the retro GUI and desktop packaging.
3. **Plan first**: the AI coding agent had to produce `PLAN.md` with milestones and "done when" criteria, and wait for approval before coding.
4. **Milestones M1-M7**: network info and CGNAT, check-host integration and stats, local scanner, retro frontend, tests, documentation, desktop launcher and `.exe` build.
5. **Human review at each stage**: plan review, screenshot review, bug reports, and real-world tests on the actual network.

The code was written with an AI coding agent working from the specification above; design decisions, review and testing were done by hand.

---

## 4. Architecture in one picture

```
Retro GUI (HTML/CSS/JS)
        │  127.0.0.1 only
FastAPI backend (async)
  ├─ network_info → ipify + UPnP + CGNAT logic
  ├─ local_scan   → asyncio TCP scanner (semaphore-limited)
  ├─ checkhost    → check-host.net client, polling, median stats
  └─ safety       → private ranges, own-IP only, rate limits
        │
pywebview window  →  PyInstaller  →  PortHole98.exe
```

---

## 5. External services used

| Service | Used for |
|---|---|
| check-host.net | TCP port checks from many countries |
| ipify | Public IPv4 / IPv6 address |
| UPnP (IGD) | Reading the router's WAN IP, with manual entry as the fallback |
| test-ipv6.com | One-off IPv6 availability test during research |

---

## 6. Open questions / next steps

- Confirm the cause of the Minecraft join lag (Anti-DoS threshold test, plugin test, upload speed).
- Verify the Public Check tab against the earlier check-host.net results on a forwarded test port.
- Add scan history, new-device alerts and UDP checks.
- Add screenshots to the README and publish a signed release if possible.