"""PyInstaller build script for PortHole 98."""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def build() -> int:
    """Run PyInstaller to package PortHole 98 into dist/PortHole98.exe."""
    icon_path = ROOT_DIR / "build" / "icon.ico"
    desktop_script = ROOT_DIR / "desktop.py"

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "PortHole98",
        "--icon",
        str(icon_path),
        "--add-data",
        "web;web",
        str(desktop_script),
    ]

    print("Running:", " ".join(cmd))
    try:
        res = subprocess.run(cmd, cwd=str(ROOT_DIR))
        return res.returncode
    except FileNotFoundError:
        alt_cmd = [sys.executable, "-m", "PyInstaller"] + cmd[1:]
        print("Falling back to:", " ".join(alt_cmd))
        res = subprocess.run(alt_cmd, cwd=str(ROOT_DIR))
        return res.returncode


if __name__ == "__main__":
    sys.exit(build())
