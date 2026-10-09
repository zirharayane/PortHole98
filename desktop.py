"""Desktop application launcher for PortHole 98 using pywebview and background uvicorn."""

import os
import socket
import sys
import threading
import time
import urllib.request
from typing import Any, Optional

# In PyInstaller --windowed mode, sys.stdout and sys.stderr are None; redirect to devnull
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import uvicorn
from app.main import app

# Inline loading page shown instantly while the backend boots
_LOADING_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>PortHole 98</title>
<style>
  body { margin:0; background:#008080; display:flex; align-items:center;
         justify-content:center; height:100vh; font-family:"MS Sans Serif",Tahoma,Arial,sans-serif; }
  .box { background:#c0c0c0; padding:24px 36px; text-align:center;
         box-shadow: inset -1px -1px #0a0a0a, inset 1px 1px #fff,
                     inset -2px -2px grey, inset 2px 2px #dfdfdf; }
  .title { background:linear-gradient(90deg,#000080,#1084d0); color:#fff;
           font-weight:bold; padding:3px 6px; margin:-24px -36px 16px; }
  .dots::after { content:''; animation: dots 1.5s steps(4,end) infinite; }
  @keyframes dots { 0%{content:''} 25%{content:'.'} 50%{content:'..'} 75%{content:'...'} }
  p { margin:8px 0; font-size:12px; color:#000; }
</style></head>
<body><div class="box">
  <div class="title">PortHole 98</div>
  <p>Starting server<span class="dots"></span></p>
  <p style="font-size:10px;color:#555;">Please wait while the backend initializes.</p>
</div></body></html>
"""


def get_free_port() -> int:
    """Find a free ephemeral TCP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def show_missing_webview2_dialog() -> None:
    """Show a native message box or terminal message if WebView2 runtime is missing."""
    title = "PortHole 98 — Missing WebView2 Runtime"
    msg = (
        "Microsoft Edge WebView2 runtime is required to run PortHole 98.\n\n"
        "Please download and install the WebView2 Evergreen Bootstrapper from:\n"
        "https://developer.microsoft.com/en-us/microsoft-edge/webview2/"
    )
    try:
        import ctypes
        # 0x10 = MB_OK | MB_ICONERROR
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)
    except Exception:
        print(f"\n[ERROR] {title}\n\n{msg}\n", file=sys.stderr)


class UvicornServerThread(threading.Thread):
    """Runs uvicorn in a daemon background thread bound strictly to 127.0.0.1."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        self.server = uvicorn.Server(self.config)

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True


def _probe_server(port: int, timeout: float = 1.0) -> bool:
    """Single non-blocking probe to check if the server is alive."""
    try:
        url = f"http://127.0.0.1:{port}/"
        req = urllib.request.Request(url, headers={"User-Agent": "PortHole98-Probe"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


class DesktopAPI:
    """Bridge exposed to JavaScript inside pywebview for native window controls."""

    def __init__(self) -> None:
        self.window: Optional[Any] = None
        self._is_maximized: bool = False

    def minimize(self) -> None:
        """Minimize the native application window."""
        if self.window:
            self.window.minimize()

    def toggle_maximize(self) -> bool:
        """Toggle maximize and restore states on the native window."""
        if self.window:
            if self._is_maximized:
                self.window.restore()
                self._is_maximized = False
            else:
                self.window.maximize()
                self._is_maximized = True
        return self._is_maximized

    def close(self) -> None:
        """Destroy the native window and quit."""
        if self.window:
            self.window.destroy()


def main() -> None:
    """Entry point for the native desktop application."""
    # 1. Verify pywebview availability
    try:
        import webview
    except ImportError:
        show_missing_webview2_dialog()
        sys.exit(1)

    # 2. Select a free random port on loopback only
    port = get_free_port()
    host = "127.0.0.1"
    target_url = f"http://{host}:{port}/"

    # 3. Start uvicorn server in background thread
    server_thread = UvicornServerThread(host=host, port=port)
    server_thread.start()

    # 4. Handle shutdown callback when window closes
    def on_window_closed() -> None:
        server_thread.stop()

    # 5. Initialize bridge API
    api = DesktopAPI()

    # 6. Background poller: once server is up, navigate the window to the real URL
    def poll_and_navigate() -> None:
        """Poll server readiness in a background thread, then navigate window."""
        for _ in range(120):  # up to 12 seconds
            if _probe_server(port, timeout=1.0):
                if api.window:
                    api.window.load_url(target_url)
                return
            time.sleep(0.1)
        # Server never came up — show error in the window
        if api.window:
            api.window.load_html(
                '<html><body style="background:#c0c0c0;font-family:Tahoma;padding:40px;">'
                '<h3 style="color:red;">Server failed to start.</h3>'
                '<p>The PortHole 98 backend did not respond after 12 seconds.</p>'
                '</body></html>'
            )

    # 7. Create native frameless pywebview window with loading page (no blocking wait)
    try:
        window = webview.create_window(
            title="PortHole 98",
            html=_LOADING_HTML,
            width=760,
            height=580,
            min_size=(640, 480),
            frameless=True,
            js_api=api,
        )
        api.window = window
        window.events.closed += on_window_closed

        # Start the background poller after webview starts
        def on_webview_started() -> None:
            t = threading.Thread(target=poll_and_navigate, daemon=True)
            t.start()

        webview.start(func=on_webview_started, gui="edgechromium")
    except Exception as exc:
        err_str = str(exc).lower()
        if "frameless" in err_str:
            # Fallback to framed window if OS/backend has issue with frameless
            print("[INFO] Falling back to standard window frame...", file=sys.stderr)
            try:
                window = webview.create_window(
                    title="PortHole 98",
                    html=_LOADING_HTML,
                    width=760,
                    height=580,
                    min_size=(640, 480),
                    frameless=False,
                    js_api=api,
                )
                api.window = window
                window.events.closed += on_window_closed
                webview.start(func=on_webview_started, gui="edgechromium")
            except Exception as exc_fallback:
                print(f"[ERROR] Native window fallback failed: {exc_fallback}", file=sys.stderr)
        elif "webview2" in err_str or "edgechromium" in err_str or "activex" in err_str:
            show_missing_webview2_dialog()
        else:
            print(f"[ERROR] Failed to start native window: {exc}", file=sys.stderr)
    finally:
        server_thread.stop()


if __name__ == "__main__":
    main()
