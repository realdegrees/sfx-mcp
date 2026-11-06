# SFX-MCP

FastMCP 3.4+ server for game sound effects: find and download CC0 sounds from the
[FreeSound API](https://freesound.org/apiv2), then shape, layer, loop and vary them with
ffmpeg, guided by a built-in sound-design ruleset. Everything it makes plays in the web UI.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- FreeSound API credential ([apply here](https://freesound.org/apiv2/apply)): the API key
  (client secret) and the client ID. Set its callback URL to
  `https://freesound.org/home/app_permissions/permission_granted/`.
- ffmpeg with `rubberband` and `afir` (on Windows: `winget install Gyan.FFmpeg`). Put it on
  PATH or set `FFMPEG_DIR` in `.env`.

## Setup

```bash
# Clone and enter directory
cd sfx-mcp

# Create .env with your API key
cp .env.example .env
# Edit .env: set FREESOUND_API_KEY, FREESOUND_CLIENT_ID (and FFMPEG_DIR if needed)

# Install dependencies
uv sync

# Run in stdio mode (for Claude Desktop, Cursor, etc.)
uv run python -m sfx_mcp

# Or run in HTTP mode (for webapp integration)
uv run python run_server.py
# Listens on http://127.0.0.1:11120
# MCP streamable-HTTP endpoint: http://127.0.0.1:11120/mcp (both spellings work;
# a path-alias middleware avoids the Mount 405; REST stays on /api/*)
# Transports: stdio (default) | --serve | --stdio | --port N | MCP_PORT=N
# Health check: http://127.0.0.1:11120/api/health
```

## Claude Code / Claude Desktop config

The server reads its settings from the environment, so pass `.env` to `uv`:

```bash
claude mcp add sfx -- uv run --env-file /path/to/sfx-mcp/.env --directory /path/to/sfx-mcp python -m sfx_mcp
```

```json
{
  "mcpServers": {
    "sfx": {
      "command": "uv",
      "args": ["run", "--env-file", "D:\\Dev\\repos\\sfx-mcp\\.env", "--directory", "D:\\Dev\\repos\\sfx-mcp", "python", "-m", "sfx_mcp"]
    }
  }
}
```

Downloading original files needs a one-time OAuth2 authorization (Freesound allows only
search and previews with the plain key): call `sfx_search(operation="authorize")`, open the
URL, click Authorize, and pass the code shown as `sfx_search(operation="authorize", code=...)`.
The token is stored in `data/oauth_token.json` and renews itself.

## Tools

### `sfx_search` (portmanteau)

| Operation | Description |
|-----------|-------------|
| `search` | Query FreeSound for CC0 sounds. Filters: query, duration_max, tags, page. |
| `download` | Download a sound by ID to local disk. |
| `tag` | Assign a user tag to a cached sound (local SQLite). |
| `list_local` | List all locally cached sounds, optionally filtered by tag. |
| `describe` | Get full metadata for a sound (name, duration, samplerate, tags, preview URL). |
| `play` | Play a locally cached sound file using the system default player or winsound (Windows). |
| `similar` | CC0 sounds acoustically similar to a sound ID ("more like this"). |
| `authorize` | One-time OAuth2 setup that `download` needs. |

### Sound design (`audio_*`)

| Tool | Description |
|------|-------------|
| `audio_guide` | Sound-design rules for game SFX: what words like "heavier", "less harsh", "distant" or "magical" mean in effects and parameters, layering rules, and recipes for impacts, whooshes, magic, UI, footsteps, creatures, ambience loops and game delivery. Sourced from published designer guides (`src/sfx_mcp/audio/design_guide.md`). |
| `audio_inspect` | Duration, peak, RMS, crest (punch), LUFS, spectral centroid and rolloff (brightness), edge silence; optional comparison against another sound. |
| `audio_process` | One sound through an effect chain, rendered to `data/renders/<name>.wav`. |
| `audio_render` | Multi-layer project: layers with sources, timeline offsets, gains, their own effect chains and repeats, master effects, peak normalization. Saved as JSON in `data/projects/` and editable. |
| `audio_project` | List, get, copy or delete saved projects. |
| `audio_variations` | Seeded random pitch, level, timing and tone per layer, for sound pools that must not repeat. |

Effects (typed, range-checked; no raw ffmpeg filter strings): `gain`, `trim`, `fade`,
`pitch` (Rubber Band or tape-style), `speed`, `eq`, `low_shelf`, `high_shelf`, `lowpass`,
`highpass`, `bandpass`, `notch`, `reverb` (convolution with a seeded generated impulse),
`echo`, `compressor`, `limiter`, `saturate`, `chorus`, `flanger`, `phaser`, `tremolo`,
`vibrato`, `reverse`, `pan`, `stereo_width`, `gate`, `trim_silence`, `pad`, `make_loop`
(equal-power crossfade of the end into the start).

Sources are a downloaded Freesound sound (`sound_id`), an earlier render (`render`), or a path
under `data/` or a folder listed in `SFX_READ_ROOTS`. Sources are never modified; renders are
written atomically. Example project:

```json
{
  "name": "hammer_impact",
  "layers": [
    {"name": "clang", "source": {"sound_id": 123}, "offset_ms": 0},
    {"name": "boom", "source": {"sound_id": 456}, "offset_ms": 30,
     "effects": [{"type": "pitch", "semitones": -7, "preserve_duration": false},
                 {"type": "lowpass", "freq_hz": 180}]},
    {"name": "debris", "source": {"sound_id": 789}, "offset_ms": 120, "gain_db": -6,
     "effects": [{"type": "reverb", "decay_s": 1.5, "wet": 0.3}]}
  ],
  "master": [{"type": "limiter", "ceiling_db": -1}],
  "channels": 1
}
```

Settings: `FFMPEG_DIR`, `SFX_READ_ROOTS`, `SFX_RENDER_PATH`, `SFX_PROJECT_PATH`,
`SFX_MAX_SOURCE_SECONDS` (900), `SFX_FFMPEG_TIMEOUT_SECONDS` (180).

### `show_sfx_browser_card`

Prefab rich card showing all locally cached sounds with names, durations, and paths.

## Ports

| Service | Port |
|---------|------|
| Backend (HTTP/MCP) | 11120 |
| Frontend (Vite dev) | 11121 |

## Webapp

`webapp/frontend/` (React + Tailwind, `bun run dev` on 11121, proxies `/api` to
11120; `bun run build` outputs to `webapp/frontend/dist/`, served by the backend
with SPA fallback). Pages: Dashboard, Sounds (search + preview + cache), Library
(renders the agent made and downloaded originals, both playable; tag filter), Tools (live MCP inventory), Logs (standard ring
buffer page), Settings, Help.

Log buffer: ring buffer (`SFX_LOG_MAX_ENTRIES`, default 2000) behind
`GET /api/logs` (+ `/stats`, `/export`, `DELETE /api/logs`). Tool calls log as
`kind: tool_call` via FastMCP middleware — no per-tool edits.

## License

MIT
