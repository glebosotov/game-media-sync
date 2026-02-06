"""Centralised configuration helpers."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ImmichConfig:
    server_url: str
    api_key: str


def get_immich_config() -> ImmichConfig:
    """Read and validate Immich env vars. Exits on missing values."""
    server_url = os.getenv("IMMICH_SERVER_URL")
    api_key = os.getenv("IMMICH_API_KEY")

    missing: list[str] = []
    if not server_url:
        missing.append("IMMICH_SERVER_URL")
    if not api_key:
        missing.append("IMMICH_API_KEY")

    if missing:
        print(f"Missing env: {', '.join(missing)}")
        sys.exit(1)

    return ImmichConfig(server_url=server_url, api_key=api_key)  # type: ignore[arg-type]
