"""Temporary-file context manager for safe cleanup after upload."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator


@contextmanager
def temp_upload_file(temp_path: str, original_path: str) -> Generator[str, None, None]:
    """Yield *temp_path*; delete it on exit when it differs from *original_path*."""
    try:
        yield temp_path
    finally:
        if temp_path != original_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
