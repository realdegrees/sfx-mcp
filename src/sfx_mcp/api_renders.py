"""REST access to rendered sounds, so the web UI can list, play and review them.

The review board is three files beside the renders folder. board.json, written by the agent,
is the current request: an id, a title and slots (what a sound is for) with a description per
candidate. When the agent starts a new request it moves the finished board into rounds/, so the
review page only ever shows one request while the library still finds every pick. reviews.json,
written by the web UI, holds the listener's verdict per render: picked, rejected, or modify with
a note saying what to change. submission.json is the hand-off: the listener sends the review,
the agent waits on the file, works through the modify notes and marks it done.
"""

from __future__ import annotations

import json
import os
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from .audio.ffmpeg import AudioError
from .audio.project import NAME_RE, check_name, project_path, render_path
from .config import config

router = APIRouter()


class Review(BaseModel):
    status: Literal["picked", "rejected", "modify"] | None = None
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def note_only_for_modify(self) -> Review:
        if self.status == "modify" and not self.note.strip():
            raise ValueError("a modify request needs a note saying what to change")
        if self.status != "modify":
            self.note = ""
        return self


class PickRemaining(BaseModel):
    slot: str | None = None


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


def _candidate(
    name: str, reviews: dict, description: str = "", source: str = "", revised: str = ""
) -> dict | None:
    if not NAME_RE.match(name):
        return None
    path = render_path(name)
    if not path.is_file():
        return None
    return {
        **_render_info(path),
        "description": description,
        "source": source,
        "revised": revised,
        "review": _review_of(reviews, name),
    }


def _review_of(reviews: dict, name: str) -> dict:
    try:
        return Review(**reviews.get(name, {})).model_dump()
    except ValueError:
        return Review().model_dump()


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
                    raw.get("revised", ""),
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


def _current_board() -> dict:
    return _read_json(_review_dir() / "board.json", {"id": "", "title": "", "slots": []})


def _all_boards() -> list[dict]:
    rounds = _review_dir() / "rounds"
    archived = (
        sorted(rounds.glob("*.json"), key=lambda p: p.stat().st_mtime) if rounds.is_dir() else []
    )
    return [_read_json(p, {"slots": []}) for p in archived] + [_current_board()]


@router.get("/board")
async def board():
    data = _current_board()
    reviews = _read_json(_review_dir() / "reviews.json", {})
    return {
        "success": True,
        "id": data.get("id", ""),
        "title": data.get("title", ""),
        "slots": _slots(data, reviews),
    }


@router.get("/picked")
async def picked():
    """Picked renders from every round, grouped by their slot; picks on no slot trail at the end."""
    reviews = _read_json(_review_dir() / "reviews.json", {})
    slots = []
    placed: set[str] = set()
    for data in _all_boards():
        for slot in _slots(data, reviews):
            kept = [
                c
                for c in slot["candidates"]
                if c["review"]["status"] == "picked" and c["name"] not in placed
            ]
            placed.update(c["name"] for c in slot["candidates"])
            if kept:
                slots.append({**slot, "round": data.get("title", ""), "candidates": kept})
    loose = [
        c
        for name, review in sorted(reviews.items())
        if review.get("status") == "picked" and name not in placed
        for c in [_candidate(name, reviews)]
        if c
    ]
    if loose:
        slots.append(
            {
                "key": "_other",
                "title": "Other picks",
                "use": "",
                "pick": "",
                "round": "",
                "candidates": loose,
            }
        )
    return {"success": True, "slots": slots}


def _counts(slots: list[dict]) -> dict:
    counts = {"picked": 0, "rejected": 0, "modify": 0, "pending": 0}
    for slot in slots:
        for c in slot["candidates"]:
            counts[c["review"]["status"] or "pending"] += 1
    return counts


@router.post("/pick-remaining")
async def pick_remaining(body: PickRemaining):
    data = _current_board()
    path = _review_dir() / "reviews.json"
    reviews = _read_json(path, {})
    picked_now = []
    for slot in _slots(data, reviews):
        if body.slot and slot["key"] != body.slot:
            continue
        for c in slot["candidates"]:
            if c["review"]["status"] is None:
                reviews[c["name"]] = Review(status="picked").model_dump()
                picked_now.append(c["name"])
    _write_json(path, reviews)
    return {"success": True, "picked": picked_now}


@router.get("/submission")
async def submission():
    return {"success": True, "submission": _read_json(_review_dir() / "submission.json", {})}


@router.post("/submission")
async def submit():
    data = _current_board()
    reviews = _read_json(_review_dir() / "reviews.json", {})
    slots = _slots(data, reviews)
    sub = {
        "status": "waiting",
        "round": data.get("id", ""),
        "submitted_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "counts": _counts(slots),
        "modify": [
            {"name": c["name"], "slot": s["title"], "note": c["review"]["note"]}
            for s in slots
            for c in s["candidates"]
            if c["review"]["status"] == "modify"
        ],
        "agent_message": "",
    }
    _write_json(_review_dir() / "submission.json", sub)
    return {"success": True, "submission": sub}


@router.post("/{name}/review")
async def set_review(name: str, review: Review):
    try:
        check_name(name)
    except AudioError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    path = _review_dir() / "reviews.json"
    reviews = _read_json(path, {})
    if review.status is None:
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
