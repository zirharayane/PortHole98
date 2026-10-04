"""Application configuration and asset path resolution."""

import os
import sys
from pathlib import Path
from dataclasses import dataclass


def resource_path(relative_path: str | Path = "") -> Path:
    """Resolve absolute path to a resource, supporting PyInstaller sys._MEIPASS."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent
    return (base / relative_path).resolve()


def get_base_dir() -> Path:
    """Return project root directory, supporting PyInstaller bundles."""
    return resource_path()


def get_resource_path(relative_path: str | Path = "") -> Path:
    """Resolve absolute path to a resource or directory."""
    return resource_path(relative_path)


@dataclass(frozen=True)
class Settings:
    """Runtime application settings."""
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))
    checkhost_cache_seconds: int = int(os.getenv("CHECKHOST_CACHE_SECONDS", "45"))
    local_scan_semaphore: int = int(os.getenv("LOCAL_SCAN_SEMAPHORE", "200"))
    local_scan_timeout: float = float(os.getenv("LOCAL_SCAN_TIMEOUT", "0.5"))
    web_dir: Path = get_resource_path("web")


settings = Settings()
