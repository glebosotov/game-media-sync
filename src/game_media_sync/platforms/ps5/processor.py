"""PS5 media processor — embed metadata, copy to output, optionally upload."""

import re
from datetime import datetime
from pathlib import Path

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)

from ...core import (
    PS5,
    MediaMetadata,
    UploadTracker,
    get_immich_config,
    set_file_timestamps,
    set_image_metadata,
    set_video_metadata,
    upload_to_immich,
)

SUPPORTED_EXTENSIONS = {".jpg", ".mp4", ".webm"}
TIMESTAMP_RE = re.compile(r"(?P<ts>\d{14})")
TRACKING_FILE = "ps5_tracker.json"


def process_files_in_folder(source_dir: str, output_dir: str, *, upload: bool = True):
    source_path = Path(source_dir).resolve()
    output_path = Path(output_dir).resolve()
    cfg = get_immich_config() if upload else None
    tracker = UploadTracker(TRACKING_FILE)

    files = []
    for f in source_path.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        m = TIMESTAMP_RE.search(f.stem)
        if m:
            dt = datetime.strptime(m.group("ts"), "%Y%m%d%H%M%S")
            creation_ts = int(dt.timestamp())
            if tracker.is_new(creation_ts):
                files.append((f, m, creation_ts))

    if not files:
        return

    ok = dup = fail = 0
    max_ts = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("{task.fields[filename]}"),
    ) as progress:
        task = progress.add_task("PS5", total=len(files), filename="")
        for source_file, match, creation_ts in files:
            name = source_file.name
            progress.update(task, filename=name)
            ext = source_file.suffix.lower()
            dest_file = output_path / source_file.relative_to(source_path)
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                dt = datetime.strptime(match.group("ts"), "%Y%m%d%H%M%S")
                meta = MediaMetadata(creation_date=dt, device=PS5)

                if ext == ".jpg":
                    ok_meta = set_image_metadata(str(source_file), str(dest_file), meta)
                else:
                    ok_meta = set_video_metadata(
                        str(source_file),
                        str(dest_file),
                        meta,
                        container=ext.lstrip("."),
                    )

                if not ok_meta:
                    progress.console.print(f"  [red]✗[/red] {name}: metadata failed")
                    fail += 1
                    progress.advance(task)
                    continue

                set_file_timestamps(str(dest_file), dt)

                if upload and cfg:
                    result = upload_to_immich(
                        str(dest_file),
                        cfg.api_key,
                        cfg.server_url,
                        device=PS5,
                        creation_date=dt,
                    )
                    if result.get("status") == "duplicate":
                        progress.console.print(
                            f"  [yellow]✓[/yellow] {name} [dim](duplicate)[/dim]"
                        )
                        dup += 1
                    else:
                        progress.console.print(f"  [green]✓[/green] {name}")
                        ok += 1
                else:
                    progress.console.print(f"  [green]✓[/green] {name}")
                    ok += 1

                max_ts = max(max_ts, creation_ts)
                tracker.record(
                    {
                        "filename": source_file.name,
                        "upload_time": datetime.now().isoformat(),
                        "creation_time": creation_ts,
                    }
                )
            except ValueError:
                progress.console.print(f"  [red]✗[/red] {name}: invalid date")
                fail += 1
            except Exception as e:
                progress.console.print(f"  [red]✗[/red] {name}: {e}")
                fail += 1
            progress.advance(task)

    if max_ts:
        tracker.update_time(max_ts)
        tracker.save()

    parts = [f"{ok} ok"]
    if dup:
        parts.append(f"{dup} duplicates")
    if fail:
        parts.append(f"{fail} failed")
    print(f"PS5: {', '.join(parts)} / {len(files)}")
