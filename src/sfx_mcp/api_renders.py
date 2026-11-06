"""REST access to rendered sounds, so the web UI can list, play and review them.

The review board is two files beside the renders folder: board.json, written by the agent,
groups renders into slots (what a sound is for) with a description per candidate; reviews.json,
written by the web UI, holds the listener's verdict and note per render.
"""

from __future__ import annotations

import json
import os
import wave
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .audio.ffmpeg import AudioError
from .audio.project import NAME_RE, check_name, project_path, render_path
from .config import config

router = APIRouter()


class Review(BaseModel):
    status: Literal["picked", "rejected"] | None = None
    note: str = Field(default="", max_length=2000)


def _review_dir() -> Path:
    return Path(config.SFX_RENDER_PATH).parent / "review"


def _read_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _duration(path: Path) -> float | None:
    try:
        with wave.open(str(path)) as w:
            return round(w.getnframes() / w.getframerate(), 3)
    except (wave.Error, OSError, EOFError):
        return None


def _render_info(path: Path) -> dict:
    return {
        "name": path.stem,
        "duration": _duration(path),
        "modified": path.stat().st_mtime,
        "has_project": project_path(path.stem).is_file(),
    }


@router.get("")
async def list_renders():
    folder = Path(config.SFX_RENDER_PATH)
    files = (
        sorted(folder.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        if folder.is_dir()
        else []
    )
    renders = [_render_info(p) for p in files if NAME_RE.match(p.stem)]
    return {"success": True, "results": renders, "total": len(renders)}


def _candidate(name: str, reviews: dict, description: str = "", source: str = "") -> dict | None:
    if not NAME_RE.match(name):
        return None
    path = render_path(name)
    if not path.is_file():
        return None
    return {
        **_render_info(path),
        "description": description,
        "source": source,
        "review": Review(**reviews.get(name, {})).model_dump(),
    }


def _slots(data: dict, reviews: dict) -> list[dict]:
    slots = []
    for slot in data.get("slots", []):
        candidates = [
            c
            for c in (
                _candidate(
                    raw.get("render", ""),
                    reviews,
                    raw.get("description", ""),
                    raw.get("source", ""),
                )
                for raw in slot.get("candidates", [])
            )
            if c
        ]
        slots.append(
            {
                "key": slot.get("key", ""),
                "title": slot.get("title", ""),
                "use": slot.get("use", ""),
                "pick": slot.get("pick", ""),
                "candidates": candidates,
            }
        )
    return slots


@router.get("/board")
async def board():
    data = _read_json(_review_dir() / "board.json", {"title": "", "slots": []})
    reviews = _read_json(_review_dir() / "reviews.json", {})
    return {"success": True, "title": data.get("title", ""), "slots": _slots(data, reviews)}


@router.get("/picked")
async def picked():
    """Picked renders grouped by their board slot; picks on no slot land in a trailing group."""
    data = _read_json(_review_dir() / "board.json", {"title": "", "slots": []})
    reviews = _read_json(_review_dir() / "reviews.json", {})
    slots = []
    placed: set[str] = set()
    for slot in _slots(data, reviews):
        kept = [c for c in slot["candidates"] if c["review"]["status"] == "picked"]
        placed.update(c["name"] for c in slot["candidates"])
        if kept:
            slots.append({**slot, "candidates": kept})
    loose = [
        c
        for name, review in sorted(reviews.items())
        if review.get("status") == "picked" and name not in placed
        for c in [_candidate(name, reviews)]
        if c
    ]
    if loose:
        slots.append(
            {"key": "_other", "title": "Other picks", "use": "", "pick": "", "candidates": loose}
        )
    return {"success": True, "slots": slots}


@router.post("/{name}/review")
async def set_review(name: str, review: Review):
    try:
        check_name(name)
    except AudioError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    path = _review_dir() / "reviews.json"
    reviews = _read_json(path, {})
    if review.status is None and not review.note:
        reviews.pop(name, None)
    else:
        reviews[name] = review.model_dump()
    _write_json(path, reviews)
    return {"success": True, "review": review.model_dump()}


@router.get("/{name}/file")
async def render_file(name: str):
    try:
        path = render_path(check_name(name))
    except AudioError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not path.is_file():
        raise HTTPException(status_code=404, detail="No such render")
    return FileResponse(path, media_type="audio/wav")
