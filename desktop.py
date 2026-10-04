"""Desktop application launcher for PortHole 98 using pywebview and background uvicorn."""

import socket
import sys
import threading
import time
import urllib.request
from typing import Optional

import uvicorn
from app.main import app


def get_free_port() -> int:
    """Find a free ephemeral TCP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def show_missing_webview2_dialog() -> None:
    """Show a native message box or terminal message if WebView2 runtime is missing."""
    title = "PortHole 98 — Missing WebView2 Runtime"
    msg = (
        "Microsoft Edge WebView2 runtime is required to run PortHole 98 in native window mode.\n\n"
        "Please download and install the WebView2 Evergreen Bootstrapper from:\n"
        "https://developer.microsoft.com/en-us/microsoft-edge/webview2/\n\n"
        "Alternatively, you can run PortHole 98 in your standard browser via:\n"
        "uvicorn app.main:app --reload"
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


def wait_for_server(port: int, max_attempts: int = 60, delay: float = 0.1) -> bool:
    """Probe the server until it responds with HTTP 200."""
    url = f"http://127.0.0.1:{port}/"
    for _ in range(max_attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PortHole98-Probe"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(delay)
    return False


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

    # 3. Start uvicorn server in background thread
    server_thread = UvicornServerThread(host=host, port=port)
    server_thread.start()

    # 4. Wait for server to respond
    if not wait_for_server(port=port):
        print("[ERROR] PortHole 98 background server failed to start.", file=sys.stderr)
        server_thread.stop()
        sys.exit(1)

    # 5. Handle shutdown callback when window closes
    def on_window_closed() -> None:
        server_thread.stop()

    # 6. Create native pywebview window
    try:
        window = webview.create_window(
            title="PortHole 98",
            url=f"http://{host}:{port}/",
            width=900,
            height=680,
            min_size=(640, 480),
        )
        window.events.closed += on_window_closed
        webview.start(gui="edgechromium")
    except Exception as exc:
        # Check if failure is related to missing WebView2
        err_str = str(exc).lower()
        if "webview2" in err_str or "edgechromium" in err_str or "activex" in err_str:
            show_missing_webview2_dialog()
        else:
            print(f"[ERROR] Failed to start native window: {exc}", file=sys.stderr)
    finally:
        server_thread.stop()


if __name__ == "__main__":
    main()
