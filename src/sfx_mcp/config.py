from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Relative paths resolve against the repo root, never the CWD: Claude Desktop
# spawns stdio servers with cwd=C:\Windows\System32 (BUG-063).
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _repo_path(value: str) -> str:
    return value if Path(value).is_absolute() else str(_REPO_ROOT / value)


@dataclass
class Config:
    FREESOUND_API_KEY: str = field(default_factory=lambda: os.getenv("FREESOUND_API_KEY", ""))
    FREESOUND_CLIENT_ID: str = field(default_factory=lambda: os.getenv("FREESOUND_CLIENT_ID", ""))
    SFX_TOKEN_PATH: str = field(
        default_factory=lambda: _repo_path(os.getenv("SFX_TOKEN_PATH", "data/oauth_token.json"))
    )
    SFX_LOCAL_PATH: str = field(
        default_factory=lambda: _repo_path(os.getenv("SFX_LOCAL_PATH", "data/sounds"))
    )
    SFX_DB_PATH: str = field(
        default_factory=lambda: _repo_path(os.getenv("SFX_DB_PATH", "data/sfx_cache.db"))
    )
    SFX_RENDER_PATH: str = field(
        default_factory=lambda: _repo_path(os.getenv("SFX_RENDER_PATH", "data/renders"))
    )
    SFX_PROJECT_PATH: str = field(
        default_factory=lambda: _repo_path(os.getenv("SFX_PROJECT_PATH", "data/projects"))
    )
    # Directory holding ffmpeg/ffprobe; empty means "find them on PATH".
    FFMPEG_DIR: str = field(default_factory=lambda: os.getenv("FFMPEG_DIR", ""))
    # Extra folders audio may be read from (os.pathsep-separated), besides this repo's data/.
    SFX_READ_ROOTS: list[str] = field(
        default_factory=lambda: [
            p for p in os.getenv("SFX_READ_ROOTS", "").split(os.pathsep) if p.strip()
        ]
    )
    SFX_MAX_SOURCE_SECONDS: float = field(
        default_factory=lambda: float(os.getenv("SFX_MAX_SOURCE_SECONDS", "900"))
    )
    SFX_FFMPEG_TIMEOUT_SECONDS: float = field(
        default_factory=lambda: float(os.getenv("SFX_FFMPEG_TIMEOUT_SECONDS", "180"))
    )
    API_BASE_URL: str = "https://freesound.org/apiv2"
    BACKEND_PORT: int = 11120
    FRONTEND_PORT: int = 11121

    @property
    def data_root(self) -> str:
        return str(_REPO_ROOT / "data")

    @property
    def has_api_key(self) -> bool:
        return bool(self.FREESOUND_API_KEY)


config = Config()
