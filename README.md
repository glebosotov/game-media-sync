# game-media-sync

Sync screenshots and clips from **Steam**, **PS5**, and **Nintendo Switch** to [Immich](https://immich.app/).

## Setup

```bash
cp .env.example .env   # fill in IMMICH_SERVER_URL and IMMICH_API_KEY
uv sync
```

## Usage

```bash
uv run python scripts/upload_steam.py
uv run python scripts/upload_ps5.py
uv run python scripts/upload_switch.py [path]
```

Paths can be configured via `.env` or passed as CLI arguments.
