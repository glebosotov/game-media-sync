"""Steam screenshot processor and uploader."""

import os
import shutil
import tempfile
from datetime import datetime

import vdf
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)

from ...core import (
    STEAM_DECK,
    MediaMetadata,
    UploadTracker,
    get_immich_config,
    set_file_timestamps,
    set_image_metadata,
    upload_to_immich,
)
from ...resolvers.game_name import get_game_name
from .utils import GetAccountId, steamdir

TRACKING_FILE = "upload_tracker.json"


def get_all_screenshots():
    try:
        user = GetAccountId()
        vdf_path = f"{steamdir}userdata/{user}/760/screenshots.vdf"
        if not os.path.exists(vdf_path):
            return []

        with open(vdf_path, "r") as f:
            d = vdf.parse(f)

        screenshots = d.get("screenshots") or d.get("Screenshots")
        if not screenshots:
            return []

        result = []
        for game in screenshots:
            for sid in screenshots[game]:
                s = screenshots[game][sid]
                if "creation" in s and "filename" in s:
                    result.append(
                        {
                            "game_id": int(game),
                            "creation_time": int(s["creation"]),
                            "filename": s["filename"],
                            "full_path": f"{steamdir}userdata/{user}/760/remote/{s['filename']}",
                        }
                    )

        result.sort(key=lambda x: x["creation_time"])
        return result
    except Exception as e:
        print(f"Error reading screenshots: {e}")
        return []


def process_screenshot(
    filepath: str,
    game_name: str | None,
    cfg,
    *,
    output_dir: str | None = None,
    upload: bool = True,
) -> dict | None:
    """Process a screenshot. Returns Immich response dict, or None if not uploaded."""
    creation_date = datetime.fromtimestamp(os.path.getmtime(filepath))
    meta = MediaMetadata(
        creation_date=creation_date, device=STEAM_DECK, game_name=game_name
    )

    if output_dir:
        subfolder = game_name or "Unknown"
        dest = os.path.join(output_dir, subfolder)
        os.makedirs(dest, exist_ok=True)
        dest_path = os.path.join(dest, os.path.basename(filepath))
    else:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            dest_path = tmp.name

    try:
        if not set_image_metadata(filepath, dest_path, meta):
            shutil.copy2(filepath, dest_path)

        set_file_timestamps(dest_path, creation_date)

        if upload and cfg:
            return upload_to_immich(
                dest_path,
                cfg.api_key,
                cfg.server_url,
                device=STEAM_DECK,
                creation_date=creation_date,
            )
        return None
    finally:
        if not output_dir:
            try:
                os.unlink(dest_path)
            except OSError:
                pass


def main(
    *,
    output_dir: str | None = None,
    upload: bool = True,
):
    if not upload and not output_dir:
        print("Nothing to do: --no-upload without --output")
        return

    cfg = get_immich_config() if upload else None
    tracker = UploadTracker(TRACKING_FILE)
    all_screenshots = get_all_screenshots()
    if not all_screenshots:
        return

    new = [s for s in all_screenshots if tracker.is_new(s["creation_time"])]
    if not new:
        return

    ok = dup = fail = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("{task.fields[filename]}"),
    ) as progress:
        task = progress.add_task("Screenshots", total=len(new), filename="")
        for s in new:
            name = s["filename"]
            progress.update(task, filename=name)

            if not os.path.exists(s["full_path"]):
                progress.console.print(f"  [red]✗[/red] {name}: not found")
                fail += 1
                progress.advance(task)
                continue

            game_name = get_game_name(s["game_id"])
            try:
                result = process_screenshot(
                    s["full_path"],
                    game_name,
                    cfg,
                    output_dir=output_dir,
                    upload=upload,
                )
                if result and result.get("status") == "duplicate":
                    progress.console.print(
                        f"  [yellow]✓[/yellow] {name} [dim](duplicate)[/dim]"
                    )
                    dup += 1
                else:
                    progress.console.print(f"  [green]✓[/green] {name}")
                    ok += 1
                tracker.record(
                    {
                        "filename": s["filename"],
                        "upload_time": datetime.now().isoformat(),
                        "creation_time": s["creation_time"],
                    }
                )
            except Exception as e:
                progress.console.print(f"  [red]✗[/red] {name}: {e}")
                fail += 1
            progress.advance(task)

    if ok or dup:
        tracker.update_time(max(s["creation_time"] for s in new))
        tracker.save()

    parts = [f"{ok} ok"]
    if dup:
        parts.append(f"{dup} duplicates")
    if fail:
        parts.append(f"{fail} failed")
    print(f"Screenshots: {', '.join(parts)} / {len(new)}")
