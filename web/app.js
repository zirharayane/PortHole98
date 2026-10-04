/**
 * PortHole 98 — Authentic Windows 95/98 Client Application
 * Zero external libraries, pure HTML5/CSS3/ES6
 */

(function () {
    "use strict";

    // Application State
    const state = {
        networkInfo: null,
        publicResults: [],
        sortField: "location",
        sortAsc: true,
        localScanPollingTimer: null,
        publicCheckPollingTimer: null,
    };

    // DOM Elements
    const elements = {
        mainWindow: document.getElementById("main-window"),
        titleBar: document.getElementById("window-title-bar"),
        btnMinimize: document.getElementById("btn-minimize"),
        btnMaximize: document.getElementById("btn-maximize"),
        btnClose: document.getElementById("btn-close"),
        taskbarApp: document.getElementById("taskbar-app"),
        startBtn: document.getElementById("start-btn"),
        startMenu: document.getElementById("start-menu"),
        trayClock: document.getElementById("tray-clock"),

        // Status bar
        statusMain: document.getElementById("status-panel-main"),
        statusIp: document.getElementById("status-panel-ip"),
        statusNodes: document.getElementById("status-panel-nodes"),

        // Network Tab
        txtPublicIpv4: document.getElementById("txt-public-ipv4"),
        txtPublicIpv6: document.getElementById("txt-public-ipv6"),
        txtRouterWan: document.getElementById("txt-router-wan"),
        btnApplyWan: document.getElementById("btn-apply-wan"),
        wanSrcLabel: document.getElementById("wan-src-label"),
        badgeIpv4: document.getElementById("badge-ipv4"),
        badgeIpv6: document.getElementById("badge-ipv6"),
        badgeCgnat: document.getElementById("badge-cgnat"),
        txtCgnatReason: document.getElementById("txt-cgnat-reason"),
        txtLocalSubnet: document.getElementById("txt-local-subnet"),
        btnRefreshNet: document.getElementById("btn-refresh-net"),

        // Local Scan Tab
        txtScanSubnet: document.getElementById("txt-scan-subnet"),
        selScanPorts: document.getElementById("sel-scan-ports"),
        btnStartLocalScan: document.getElementById("btn-start-local-scan"),
        localProgressFill: document.getElementById("local-progress-fill"),
        tableLocalResults: document.getElementById("table-local-results"),

        // Public Check Tab
        txtCheckPort: document.getElementById("txt-check-port"),
        selCheckRuns: document.getElementById("sel-check-runs"),
        btnStartPublicCheck: document.getElementById("btn-start-public-check"),
        publicProgressFill: document.getElementById("public-progress-fill"),
        tablePublicResults: document.getElementById("table-public-results"),

        // Modals
        modalOverlay: document.getElementById("modal-dialog"),
        modalTitle: document.getElementById("modal-title"),
        modalMessage: document.getElementById("modal-message"),
        modalIconContainer: document.getElementById("modal-icon-container"),
        modalBtnOk: document.getElementById("modal-btn-ok"),
        modalBtnX: document.getElementById("modal-btn-x"),
    };

    /* ==========================================================================
       SVG Retro Icons
       ========================================================================== */
    const ICONS = {
        error: `<svg viewBox="0 0 32 32" width="32" height="32">
            <circle cx="16" cy="16" r="14" fill="#c00000" stroke="#000" stroke-width="1"/>
            <line x1="10" y1="10" x2="22" y2="22" stroke="#ffffff" stroke-width="3" stroke-linecap="round"/>
            <line x1="22" y1="10" x2="10" y2="22" stroke="#ffffff" stroke-width="3" stroke-linecap="round"/>
        </svg>`,
        warning: `<svg viewBox="0 0 32 32" width="32" height="32">
            <polygon points="16,3 30,28 2,28" fill="#ffd700" stroke="#000" stroke-width="1"/>
            <rect x="14.5" y="11" width="3" height="9" fill="#000000"/>
            <rect x="14.5" y="23" width="3" height="3" fill="#000000"/>
        </svg>`,
        info: `<svg viewBox="0 0 32 32" width="32" height="32">
            <circle cx="16" cy="16" r="14" fill="#000080" stroke="#000" stroke-width="1"/>
            <rect x="14.5" y="8" width="3" height="3" fill="#ffffff"/>
            <rect x="14.5" y="14" width="3" height="10" fill="#ffffff"/>
            <rect x="11.5" y="14" width="3" height="3" fill="#ffffff"/>
            <rect x="11.5" y="22" width="9" height="2" fill="#ffffff"/>
        </svg>`,
    };

    /* ==========================================================================
       Taskbar Clock
       ========================================================================== */
    function updateClock() {
        const now = new Date();
        let hours = now.getHours();
        const minutes = String(now.getMinutes()).padStart(2, "0");
        const ampm = hours >= 12 ? "PM" : "AM";
        hours = hours % 12 || 12;
        elements.trayClock.textContent = `${hours}:${minutes} ${ampm}`;
    }
    setInterval(updateClock, 1000);
    updateClock();

    /* ==========================================================================
       Modal Dialog Controller
       ========================================================================== */
    function showModal(title, messageHtml, type = "info") {
        elements.modalTitle.textContent = title;
        elements.modalMessage.innerHTML = messageHtml;
        elements.modalIconContainer.innerHTML = ICONS[type] || ICONS.info;
        elements.modalOverlay.classList.add("active");
    }

    function closeModal() {
        elements.modalOverlay.classList.remove("active");
    }

    elements.modalBtnOk.addEventListener("click", closeModal);
    elements.modalBtnX.addEventListener("click", closeModal);
    elements.modalOverlay.addEventListener("click", (e) => {
        if (e.target === elements.modalOverlay) closeModal();
    });

    /* ==========================================================================
       Window Dragging Logic
       ========================================================================== */
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let windowStartX = 0;
    let windowStartY = 0;

    elements.titleBar.addEventListener("mousedown", (e) => {
        if (e.target.closest(".title-bar-controls")) return;
        isDragging = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;

        const rect = elements.mainWindow.getBoundingClientRect();
        windowStartX = rect.left;
        windowStartY = rect.top;

        // Disengage centering transform on first drag
        elements.mainWindow.style.transform = "none";
        elements.mainWindow.style.left = `${windowStartX}px`;
        elements.mainWindow.style.top = `${windowStartY}px`;
    });

    window.addEventListener("mousemove", (e) => {
        if (!isDragging) return;
        const deltaX = e.clientX - dragStartX;
        const deltaY = e.clientY - dragStartY;

        let newX = windowStartX + deltaX;
        let newY = windowStartY + deltaY;

        // Boundary clamp
        const maxX = window.innerWidth - 60;
        const maxY = window.innerHeight - 50;
        newX = Math.max(0, Math.min(newX, maxX));
        newY = Math.max(0, Math.min(newY, maxY));

        elements.mainWindow.style.left = `${newX}px`;
        elements.mainWindow.style.top = `${newY}px`;
    });

    window.addEventListener("mouseup", () => {
        isDragging = false;
    });

    /* ==========================================================================
       Window Controls (Minimize, Maximize, Close, Taskbar)
       ========================================================================== */
    let isMaximized = false;
    let preMaxRect = null;

    elements.btnMinimize.addEventListener("click", () => {
        elements.mainWindow.style.display = "none";
        elements.taskbarApp.classList.remove("active");
    });

    elements.taskbarApp.addEventListener("click", () => {
        if (elements.mainWindow.style.display === "none") {
            elements.mainWindow.style.display = "flex";
            elements.taskbarApp.classList.add("active");
        } else {
            elements.mainWindow.style.display = "none";
            elements.taskbarApp.classList.remove("active");
        }
    });

    elements.btnMaximize.addEventListener("click", () => {
        if (!isMaximized) {
            preMaxRect = {
                left: elements.mainWindow.style.left,
                top: elements.mainWindow.style.top,
                width: elements.mainWindow.style.width,
                transform: elements.mainWindow.style.transform,
            };
            elements.mainWindow.style.transform = "none";
            elements.mainWindow.style.left = "0px";
            elements.mainWindow.style.top = "0px";
            elements.mainWindow.style.width = "100vw";
            elements.mainWindow.style.height = "calc(100vh - 28px)";
            isMaximized = true;
        } else {
            if (preMaxRect) {
                elements.mainWindow.style.left = preMaxRect.left;
                elements.mainWindow.style.top = preMaxRect.top;
                elements.mainWindow.style.width = preMaxRect.width;
                elements.mainWindow.style.transform = preMaxRect.transform;
            }
            elements.mainWindow.style.height = "auto";
            isMaximized = false;
        }
    });

    elements.btnClose.addEventListener("click", () => {
        showModal(
            "Exit PortHole 98",
            "<p>To close the application, please close your browser tab or terminate the process in the terminal.</p>",
            "info"
        );
    });

    /* ==========================================================================
       Menu Bar & Start Menu
       ========================================================================== */
    function closeAllMenus() {
        document.querySelectorAll(".menu-item").forEach(m => m.classList.remove("open"));
        elements.startMenu.style.display = "none";
        elements.startBtn.classList.remove("active");
    }

    document.querySelectorAll(".menu-item").forEach(menu => {
        menu.addEventListener("click", (e) => {
            e.stopPropagation();
            const isOpen = menu.classList.contains("open");
            closeAllMenus();
            if (!isOpen) menu.classList.add("open");
        });
    });

    elements.startBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = elements.startMenu.style.display === "block";
        closeAllMenus();
        if (!isOpen) {
            elements.startMenu.style.display = "block";
            elements.startBtn.classList.add("active");
        }
    });

    window.addEventListener("click", () => {
        closeAllMenus();
    });

    // Menu Item Actions
    document.getElementById("menu-refresh").addEventListener("click", () => loadNetworkInfo());
    document.getElementById("start-menu-refresh").addEventListener("click", () => loadNetworkInfo());

    function showAboutDialog() {
        showModal(
            "About PortHole 98",
            `<div style="text-align: left;">
                <p style="font-weight: bold; font-size: 13px; margin-bottom: 6px;">PortHole 98 — Version 1.0</p>
                <p style="margin-bottom: 6px;">A classic Windows 95/98 network diagnostic system.</p>
                <p style="margin-bottom: 6px; color: #555;">Features:</p>
                <ul style="margin-left: 18px; margin-bottom: 8px;">
                    <li>Public IPv4 & IPv6 Discovery via ipify</li>
                    <li>UPnP IGD Router WAN IP & CGNAT Detection</li>
                    <li>Asynchronous Concurrent Local Subnet Port Scanner</li>
                    <li>Global Multi-Continent Latency Testing via check-host.net</li>
                </ul>
                <div class="bevel-sunken" style="padding: 6px; background: #fff; margin-top: 8px; font-style: italic; color: #b00000; font-weight: bold;">
                    Notice: Only scan networks you own or have permission to test.
                </div>
            </div>`,
            "info"
        );
    }

    document.getElementById("menu-about").addEventListener("click", showAboutDialog);
    document.getElementById("start-menu-about").addEventListener("click", showAboutDialog);

    function runAllChecks() {
        loadNetworkInfo().then(() => {
            startLocalScan();
            startPublicCheck();
        });
    }

    document.getElementById("menu-run-all").addEventListener("click", runAllChecks);
    document.getElementById("start-menu-run-all").addEventListener("click", runAllChecks);

    document.getElementById("menu-exit").addEventListener("click", () => elements.btnClose.click());
    document.getElementById("start-menu-exit").addEventListener("click", () => elements.btnClose.click());

    /* ==========================================================================
       Tab Navigation
       ========================================================================== */
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-tab");
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const panel = document.getElementById(targetId);
            if (panel) panel.classList.add("active");
        });
    });

    /* ==========================================================================
       API Communications — Tab 1: Network Information
       ========================================================================== */
    async function loadNetworkInfo(manualWanIp = null) {
        elements.statusMain.textContent = "Querying network configuration...";
        document.body.classList.add("busy");

        try {
            let url = "/api/network";
            if (manualWanIp && manualWanIp.trim()) {
                url += `?wan_ip=${encodeURIComponent(manualWanIp.trim())}`;
            }

            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP error ${resp.status}`);
            const data = await resp.json();
            state.networkInfo = data;

            // Render Public IPv4
            if (data.public_ipv4) {
                elements.txtPublicIpv4.value = data.public_ipv4;
                elements.badgeIpv4.textContent = "CONNECTED";
                elements.badgeIpv4.className = "indicator-tag tag-green";
                elements.statusIp.textContent = `IP: ${data.public_ipv4}`;
            } else {
                elements.txtPublicIpv4.value = "Unavailable";
                elements.badgeIpv4.textContent = "FAILED";
                elements.badgeIpv4.className = "indicator-tag tag-red";
                elements.statusIp.textContent = "IP: Offline";
            }

            // Render Public IPv6
            if (data.public_ipv6) {
                elements.txtPublicIpv6.value = data.public_ipv6;
                elements.badgeIpv6.textContent = "ACTIVE";
                elements.badgeIpv6.className = "indicator-tag tag-green";
            } else {
                elements.txtPublicIpv6.value = "None (IPv4 only or unsupported)";
                elements.badgeIpv6.textContent = "NONE";
                elements.badgeIpv6.className = "indicator-tag tag-gray";
            }

            // Render Router WAN IP
            if (data.router_wan_ip) {
                elements.txtRouterWan.value = data.router_wan_ip;
                elements.wanSrcLabel.textContent = manualWanIp ? "(Manual override)" : "(UPnP IGD)";
            } else {
                elements.txtRouterWan.value = "";
                elements.txtRouterWan.placeholder = "UPnP unavailable; enter IP manually";
                elements.wanSrcLabel.textContent = "(Not detected)";
            }

            // Render CGNAT Status
            if (data.cgnat) {
                elements.badgeCgnat.textContent = "YES (CGNAT / Upstream NAT)";
                elements.badgeCgnat.className = "indicator-tag tag-red";
            } else {
                elements.badgeCgnat.textContent = "NO (Direct Public IP)";
                elements.badgeCgnat.className = "indicator-tag tag-green";
            }
            elements.txtCgnatReason.value = data.reason || "N/A";

            // Render Local Subnet & Prefill Local Scan Tab
            if (data.local_subnet) {
                elements.txtLocalSubnet.value = data.local_subnet;
                if (!elements.txtScanSubnet.value || elements.txtScanSubnet.value.includes("192.168.1.0")) {
                    elements.txtScanSubnet.value = data.local_subnet;
                }
            }

            elements.statusMain.textContent = "Network discovery complete.";

            // If CGNAT is detected and user hasn't seen the notice yet, inform them
            if (data.cgnat && !sessionStorage.getItem("cgnat_notified")) {
                sessionStorage.setItem("cgnat_notified", "1");
                showModal(
                    "CGNAT Notice",
                    `<p><b>Carrier-Grade NAT (CGNAT) Detected!</b></p>
                     <p style="margin-top: 6px;">${data.reason}</p>
                     <p style="margin-top: 6px; font-size: 10px; color: #555;">Note: Port forwarding on your local router will not make ports reachable from the internet under CGNAT without an ISP public IP or tunnel.</p>`,
                    "warning"
                );
            }

        } catch (err) {
            elements.statusMain.textContent = "Network query failed.";
            showModal("Network Error", `<p>Failed to query network configuration:</p><p style="color: red; margin-top: 4px;">${err.message}</p>`, "error");
        } finally {
            document.body.classList.remove("busy");
        }
    }

    elements.btnRefreshNet.addEventListener("click", () => loadNetworkInfo());
    elements.btnApplyWan.addEventListener("click", () => {
        const val = elements.txtRouterWan.value.trim();
        loadNetworkInfo(val);
    });

    /* ==========================================================================
       API Communications — Tab 2: Local Subnet Scanner
       ========================================================================== */
    async function startLocalScan() {
        const subnet = elements.txtScanSubnet.value.trim();
        const ports = elements.selScanPorts.value;

        if (!subnet) {
            showModal("Input Required", "<p>Please specify a target private subnet (e.g. 192.168.1.0/24).</p>", "warning");
            return;
        }

        elements.btnStartLocalScan.disabled = true;
        document.body.classList.add("busy");
        elements.localProgressFill.style.width = "0%";
        elements.statusMain.textContent = `Scanning local network (${subnet})...`;

        // Clear existing table
        elements.tableLocalResults.querySelector("tbody").innerHTML = `
            <tr><td colspan="3" style="text-align: center; color: #000080; padding: 20px;">Scanning in progress. Probing hosts and open ports...</td></tr>
        `;

        try {
            const resp = await fetch("/api/scan/local", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ subnet, ports }),
            });

            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || `Scan initiation failed (HTTP ${resp.status})`);
            }

            const { job_id } = await resp.json();
            pollLocalScan(job_id);

        } catch (err) {
            document.body.classList.remove("busy");
            elements.btnStartLocalScan.disabled = false;
            elements.statusMain.textContent = "Scan failed.";
            showModal("Scan Error", `<p>${err.message}</p>`, "error");
        }
    }

    function pollLocalScan(jobId) {
        if (state.localScanPollingTimer) clearInterval(state.localScanPollingTimer);

        state.localScanPollingTimer = setInterval(async () => {
            try {
                const resp = await fetch(`/api/scan/local/${jobId}`);
                if (!resp.ok) throw new Error("Failed to poll scan status");
                const data = await resp.json();

                // Update progress bar
                const pct = Math.max(5, Math.min(100, data.progress || 0));
                elements.localProgressFill.style.width = `${pct}%`;
                elements.statusMain.textContent = `Scanning local network (${pct}%)...`;

                if (data.status === "completed") {
                    clearInterval(state.localScanPollingTimer);
                    document.body.classList.remove("busy");
                    elements.btnStartLocalScan.disabled = false;
                    elements.localProgressFill.style.width = "100%";
                    renderLocalDevices(data.devices || []);
                    elements.statusMain.textContent = `Scan complete. Found ${data.devices.length} devices with open ports.`;
                } else if (data.status === "failed") {
                    clearInterval(state.localScanPollingTimer);
                    document.body.classList.remove("busy");
                    elements.btnStartLocalScan.disabled = false;
                    elements.statusMain.textContent = "Scan job failed.";
                    showModal("Scan Error", `<p>${data.error || "An unknown error occurred during scan."}</p>`, "error");
                }
            } catch (err) {
                clearInterval(state.localScanPollingTimer);
                document.body.classList.remove("busy");
                elements.btnStartLocalScan.disabled = false;
                showModal("Connection Lost", `<p>Lost connection to scan worker: ${err.message}</p>`, "error");
            }
        }, 600);
    }

    function renderLocalDevices(devices) {
        const tbody = elements.tableLocalResults.querySelector("tbody");
        if (!devices || devices.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: #808080; padding: 20px;">No open ports discovered on this subnet.</td></tr>`;
            return;
        }

        tbody.innerHTML = devices.map(dev => {
            const portsStr = dev.open_ports.map(p => `<span style="font-weight: bold; color: #000080;">${p.port}</span> (${p.service})`).join(", ");
            const hostnameStr = dev.hostname ? dev.hostname : `<span style="color: #808080;">—</span>`;
            return `<tr>
                <td style="font-weight: bold;">${dev.ip}</td>
                <td>${hostnameStr}</td>
                <td>${portsStr}</td>
            </tr>`;
        }).join("");
    }

    elements.btnStartLocalScan.addEventListener("click", startLocalScan);

    /* ==========================================================================
       API Communications — Tab 3: Public Reachability Check
       ========================================================================== */
    async function startPublicCheck() {
        const portVal = parseInt(elements.txtCheckPort.value, 10);
        const runsVal = parseInt(elements.selCheckRuns.value, 10);

        if (isNaN(portVal) || portVal < 1 || portVal > 65535) {
            showModal("Invalid Port", "<p>Please enter a valid TCP port number between 1 and 65535.</p>", "warning");
            return;
        }

        elements.btnStartPublicCheck.disabled = true;
        document.body.classList.add("busy");
        elements.publicProgressFill.style.width = "10%";
        elements.statusMain.textContent = `Checking port ${portVal} reachability from 5 continents...`;

        elements.tablePublicResults.querySelector("tbody").innerHTML = `
            <tr><td colspan="7" style="text-align: center; color: #000080; padding: 20px;">Testing global TCP connectivity across 5 continents...</td></tr>
        `;

        try {
            const resp = await fetch("/api/check/public", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ port: portVal, runs: runsVal }),
            });

            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || `Check initiation failed (HTTP ${resp.status})`);
            }

            const { job_id } = await resp.json();
            pollPublicCheck(job_id);

        } catch (err) {
            document.body.classList.remove("busy");
            elements.btnStartPublicCheck.disabled = false;
            elements.statusMain.textContent = "Public check failed.";
            showModal("Check Error", `<p>${err.message}</p>`, "error");
        }
    }

    function pollPublicCheck(jobId) {
        if (state.publicCheckPollingTimer) clearInterval(state.publicCheckPollingTimer);
        let progressTick = 15;

        state.publicCheckPollingTimer = setInterval(async () => {
            progressTick = Math.min(progressTick + 8, 92);
            elements.publicProgressFill.style.width = `${progressTick}%`;

            try {
                const resp = await fetch(`/api/check/public/${jobId}`);
                if (!resp.ok) throw new Error("Failed to poll check status");
                const data = await resp.json();

                if (data.status === "completed") {
                    clearInterval(state.publicCheckPollingTimer);
                    document.body.classList.remove("busy");
                    elements.btnStartPublicCheck.disabled = false;
                    elements.publicProgressFill.style.width = "100%";
                    state.publicResults = data.results || [];
                    renderPublicResults();
                    elements.statusMain.textContent = `Check complete: ${state.publicResults.length}/5 locations tested.`;
                } else if (data.status === "failed") {
                    clearInterval(state.publicCheckPollingTimer);
                    document.body.classList.remove("busy");
                    elements.btnStartPublicCheck.disabled = false;
                    elements.statusMain.textContent = "Check job failed.";
                    showModal("Check Error", `<p>${data.error || "An unknown error occurred during check."}</p>`, "error");
                }
            } catch (err) {
                clearInterval(state.publicCheckPollingTimer);
                document.body.classList.remove("busy");
                elements.btnStartPublicCheck.disabled = false;
                showModal("Connection Lost", `<p>Lost connection to check worker: ${err.message}</p>`, "error");
            }
        }, 1200);
    }

    function renderPublicResults() {
        const tbody = elements.tablePublicResults.querySelector("tbody");
        if (!state.publicResults || state.publicResults.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #808080; padding: 20px;">No results available.</td></tr>`;
            return;
        }

        // Sort results
        const sorted = [...state.publicResults].sort((a, b) => {
            let vA = a[state.sortField];
            let vB = b[state.sortField];
            if (vA === null || vA === undefined) vA = 999999;
            if (vB === null || vB === undefined) vB = 999999;
            if (typeof vA === "string") {
                return state.sortAsc ? vA.localeCompare(vB) : vB.localeCompare(vA);
            }
            return state.sortAsc ? vA - vB : vB - vA;
        });

        tbody.innerHTML = sorted.map(row => {
            const isOpen = row.status.toLowerCase().includes("open");
            const statusClass = isOpen ? "color: #008000; font-weight: bold;" : "color: #b00000;";
            const medStr = row.median !== null ? `${row.median} ms` : `<span style="color: #808080;">—</span>`;
            const minStr = row.min !== null ? `${row.min} ms` : `<span style="color: #808080;">—</span>`;
            const maxStr = row.max !== null ? `${row.max} ms` : `<span style="color: #808080;">—</span>`;

            return `<tr>
                <td style="font-weight: bold;">${row.location}</td>
                <td>${row.region}</td>
                <td style="${statusClass}">${row.status}</td>
                <td style="font-weight: bold;">${medStr}</td>
                <td>${minStr}</td>
                <td>${maxStr}</td>
                <td>${row.failed}</td>
            </tr>`;
        }).join("");
    }

    // Column Sorting
    elements.tablePublicResults.querySelectorAll("th[data-sort]").forEach(th => {
        th.addEventListener("click", () => {
            const field = th.getAttribute("data-sort");
            if (state.sortField === field) {
                state.sortAsc = !state.sortAsc;
            } else {
                state.sortField = field;
                state.sortAsc = true;
            }

            elements.tablePublicResults.querySelectorAll("th").forEach(h => {
                const text = h.textContent.replace(/ [▲▼]/g, "");
                h.textContent = text;
            });
            th.textContent = `${th.textContent} ${state.sortAsc ? "▲" : "▼"}`;
            renderPublicResults();
        });
    });

    elements.btnStartPublicCheck.addEventListener("click", startPublicCheck);

    /* ==========================================================================
       Initial Bootstrapping
       ========================================================================== */
    window.addEventListener("DOMContentLoaded", () => {
        loadNetworkInfo();
    });

})();
