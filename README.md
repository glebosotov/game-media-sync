# game-media-sync

Sync screenshots and clips from **Steam**, **PS5**, and **Nintendo Switch 2** to [Immich](https://immich.app/).

## Setup

```bash
cp .env.example .env   # fill in values
uv sync
```

## Usage

```bash
# Steam screenshots
gms steam

# Steam game clips
gms steam-clips

# PS5 — embed metadata and copy to output folder
gms ps5 --source /path/to/ps5 --output /path/to/output

# Nintendo Switch 2
gms switch /path/to/switch/media
```

All paths can also be set via environment variables in `.env`:

| Variable | Description |
| --- | --- |
| `IMMICH_SERVER_URL` | Immich server URL |
| `IMMICH_API_KEY` | Immich API key |
| `PS5_SOURCE_PATH` | PS5 source folder |
| `PS5_OUTPUT_PATH` | PS5 output folder |
| `SWITCH2_SOURCE_PATH` | Switch 2 source folder |
| `EXIFTOOL_PATH` | Custom exiftool path (optional) |
