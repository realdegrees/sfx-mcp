"""Locating and running ffmpeg/ffprobe. Always argument lists, never a shell."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from ..config import config


class AudioError(RuntimeError):
    pass


@lru_cache(maxsize=None)
def binary(name: str) -> str:
    if config.FFMPEG_DIR:
        candidate = Path(config.FFMPEG_DIR) / (name + (".exe" if os.name == "nt" else ""))
        if candidate.is_file():
            return str(candidate)
        raise AudioError(f"{name} not found in FFMPEG_DIR={config.FFMPEG_DIR}")
    found = shutil.which(name)
    if not found:
        raise AudioError(
            f"{name} not found. Install ffmpeg (a build with rubberband, e.g. the gyan.dev "
            "full build) and put it on PATH or set FFMPEG_DIR."
        )
    return found


@lru_cache(maxsize=1)
def filters() -> frozenset[str]:
    out = run([binary("ffmpeg"), "-hide_banner", "-filters"]).stdout
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "->" in parts[2]:
            names.add(parts[1])
    return frozenset(names)


def require_filter(name: str) -> None:
    if name not in filters():
        raise AudioError(
            f"This ffmpeg build lacks the '{name}' filter. Use a full build (gyan.dev on "
            "Windows, or a distro package built with librubberband)."
        )


def run(args: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout or config.SFX_FFMPEG_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as e:
        raise AudioError(f"{Path(args[0]).stem} timed out after {e.timeout:.0f}s") from e
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-8:])
        raise AudioError(f"{Path(args[0]).stem} failed:\n{tail}")
    return result


def probe(path: str) -> dict:
    out = run(
        [
            binary("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name:stream=codec_name,sample_rate,channels,bits_per_sample",
            "-select_streams",
            "a:0",
            "-of",
            "json",
            path,
        ]
    ).stdout
    data = json.loads(out)
    streams = data.get("streams") or []
    if not streams:
        raise AudioError(f"No audio stream in {path}")
    s = streams[0]
    fmt = data.get("format") or {}
    return {
        "duration_s": float(fmt.get("duration") or 0),
        "sample_rate": int(s.get("sample_rate") or 0),
        "channels": int(s.get("channels") or 0),
        "codec": s.get("codec_name"),
        "bits_per_sample": int(s.get("bits_per_sample") or 0) or None,
        "container": fmt.get("format_name"),
    }
