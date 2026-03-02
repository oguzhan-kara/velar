import dataclasses
import json
import os
from pathlib import Path

DEFAULTS = {
    "backend_url": "http://localhost:8000",
    "wake_sensitivity": 0.5,
    "audio_device_index": None,  # None = sounddevice default
}


@dataclasses.dataclass
class DaemonConfig:
    backend_url: str
    wake_sensitivity: float
    audio_device_index: int | None


def load_config() -> DaemonConfig:
    """Load from ~/.velar/daemon.json; env var VELAR_BACKEND_URL overrides backend_url."""
    config_path = Path.home() / ".velar" / "daemon.json"
    data = dict(DEFAULTS)
    if config_path.exists():
        with config_path.open() as f:
            data.update(json.load(f))
    # Env override for backend URL (critical for dev vs. production)
    if url := os.environ.get("VELAR_BACKEND_URL"):
        data["backend_url"] = url
    return DaemonConfig(
        backend_url=data["backend_url"],
        wake_sensitivity=float(data["wake_sensitivity"]),
        audio_device_index=data.get("audio_device_index"),
    )
