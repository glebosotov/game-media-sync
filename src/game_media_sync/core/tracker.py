"""Generic upload tracker — persists progress to a JSON file."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


class UploadTracker:
    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._data = self._load()

    @property
    def last_upload_time(self) -> int:
        return self._data.get("last_upload_time", 0)

    @property
    def uploaded_items(self) -> List[Dict[str, Any]]:
        return self._data.setdefault("uploaded_items", [])

    def is_new(self, creation_time: int) -> bool:
        return creation_time > self.last_upload_time

    def record(self, entry: Dict[str, Any]) -> None:
        self.uploaded_items.append(entry)

    def update_time(self, timestamp: int) -> None:
        self._data["last_upload_time"] = timestamp

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {"last_upload_time": 0, "uploaded_items": []}
