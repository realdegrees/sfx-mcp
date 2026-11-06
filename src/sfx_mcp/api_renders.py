"""REST access to rendered sounds, so the web UI can list and play them."""

from __future__ import annotations

import wave
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .audio.ffmpeg import AudioError
from .audio.project import NAME_RE, check_name, project_path, render_path
from .config import config

router = APIRouter()


def _duration(path: Path) -> float | None:
    try:
        with wave.open(str(path)) as w:
            return round(w.getnframes() / w.getframerate(), 3)
    except (wave.Error, OSError, EOFError):
        return None


@router.get("")
async def list_renders():
    folder = Path(config.SFX_RENDER_PATH)
    files = sorted(folder.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
    renders = [
        {
            "name": p.stem,
            "duration": _duration(p),
            "modified": p.stat().st_mtime,
            "has_project": project_path(p.stem).is_file(),
        }
        for p in files
        if NAME_RE.match(p.stem)
    ]
    return {"success": True, "results": renders, "total": len(renders)}


@router.get("/{name}/file")
async def render_file(name: str):
    try:
        path = render_path(check_name(name))
    except AudioError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not path.is_file():
        raise HTTPException(status_code=404, detail="No such render")
    return FileResponse(path, media_type="audio/wav")
