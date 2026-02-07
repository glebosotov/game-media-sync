# game-media-sync

[![Lint](https://github.com/glebosotov/game-media-sync/actions/workflows/lint.yml/badge.svg)](https://github.com/glebosotov/game-media-sync/actions/workflows/lint.yml)

Sync screenshots and clips from **Steam**, **PS5**, and **Nintendo Switch 2** to [Immich](https://immich.app/).

<img src="img/sync-media-to-immich.webp" alt="Sync media to Immich" width="600">

> **⚠️ Warning**  
> This project was made with heavy AI assiatance. Although it works for me it may require some tweaks for you. Feel free to open an issue in case of troubles, but keep in mind that you are responsible for your files.

## Setup

```bash
cp .env.example .env   # fill in values
uv sync
```

## Usage

All platforms upload to Immich by default. Add `--no-upload` to skip.

```bash
# Steam screenshots (auto-detects Steam directory)
gmedia steam
gmedia steam --output /path/to/output --no-upload

# Steam game clips
gmedia steam-clips
gmedia steam-clips --output /path/to/clips

# PS5
gmedia ps5 --source /path/to/ps5 --output /path/to/output

# Nintendo Switch 2
gmedia switch --source /path/to/switch --output /path/to/output
```

Environment variables (`.env`):

| Variable | Description |
| --- | --- |
| `IMMICH_SERVER_URL` | Immich server URL |
| `IMMICH_API_KEY` | Immich API key |
| `EXIFTOOL_PATH` | Custom exiftool path (optional) |
