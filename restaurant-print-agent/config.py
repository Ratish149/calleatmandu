import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def get_base_dir() -> Path:
    """
    Returns the root directory where the binary or script is located.
    Ensures portable paths when running as a compiled PyInstaller executable.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


class Config:
    """
    Lightweight, immutable configuration container for the print agent.
    Loads settings from config.json located beside the executable.
    """

    def __init__(self, config_path: Optional[Any] = None):
        self.base_dir = get_base_dir()
        self.config_path = Path(config_path) if config_path else (self.base_dir / "config.json")
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Reads config.json from disk."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found at: {self.config_path}\n"
                f"Please create config.json based on config.json.example"
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        self._validate()

    def _validate(self) -> None:
        """Ensures all mandatory configuration keys are specified."""
        required_keys = ["server_url", "branch_id", "printer_name"]
        missing = [k for k in required_keys if not self.data.get(k)]
        if missing:
            raise ValueError(f"Missing required configuration fields in config.json: {', '.join(missing)}")

    @property
    def server_url(self) -> str:
        return str(self.data.get("server_url", "")).strip()

    @property
    def branch_id(self) -> Any:
        return self.data.get("branch_id")

    @property
    def printer_name(self) -> str:
        return str(self.data.get("printer_name", "")).strip()

    @property
    def paper_width_mm(self) -> int:
        return int(self.data.get("paper_width_mm", 80))

    @property
    def reconnect_interval_max(self) -> int:
        return int(self.data.get("reconnect_interval_max", 30))

    def get_websocket_url(self) -> str:
        """
        Builds complete WebSocket connection URL.
        Example: wss://api.example.com/ws/printer/15/
        """
        url = self.server_url
        if not url.endswith("/"):
            url += "/"

        branch_str = str(self.branch_id)
        if not url.rstrip("/").endswith(f"/{branch_str}"):
            url = f"{url}{branch_str}/"

        return url
