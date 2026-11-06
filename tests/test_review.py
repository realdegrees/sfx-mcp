"""Review board REST: the agent's board.json grouped with the listener's verdicts."""

from __future__ import annotations

import json
import wave

import pytest
from fastapi.testclient import TestClient

from sfx_mcp.config import config
from sfx_mcp.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    renders = tmp_path / "renders"
    renders.mkdir()
    monkeypatch.setattr(config, "SFX_RENDER_PATH", str(renders))
    monkeypatch.setattr(config, "SFX_PROJECT_PATH", str(tmp_path / "projects"))
    for name in ("sea_a", "sea_b"):
        with wave.open(str(renders / f"{name}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(b"\0\0" * 4800)
    review = tmp_path / "review"
    review.mkdir()
    (review / "board.json").write_text(
        json.dumps(
            {
                "title": "Beds",
                "slots": [
                    {
                        "key": "ocean",
                        "title": "Ocean bed",
                        "use": "2D loop",
                        "candidates": [
                            {"render": "sea_a", "description": "far"},
                            {"render": "sea_b", "description": "near"},
                            {"render": "missing", "description": "never rendered"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return TestClient(app), review


def test_board_lists_existing_candidates_with_empty_reviews(client):
    c, _ = client
    data = c.get("/api/renders/board").json()
    slot = data["slots"][0]
    assert data["title"] == "Beds"
    assert [x["name"] for x in slot["candidates"]] == ["sea_a", "sea_b"]
    assert slot["candidates"][0]["review"] == {"status": None, "note": ""}
    assert slot["candidates"][0]["duration"] == 0.1


def test_review_is_saved_and_cleared(client):
    c, review = client
    assert (
        c.post("/api/renders/sea_a/review", json={"status": "picked", "note": "nice"}).status_code
        == 200
    )
    saved = json.loads((review / "reviews.json").read_text(encoding="utf-8"))
    assert saved == {"sea_a": {"status": "picked", "note": "nice"}}
    assert (
        c.get("/api/renders/board").json()["slots"][0]["candidates"][0]["review"]["status"]
        == "picked"
    )
    c.post("/api/renders/sea_a/review", json={"status": None, "note": ""})
    assert json.loads((review / "reviews.json").read_text(encoding="utf-8")) == {}


def test_review_rejects_bad_status_and_name(client):
    c, _ = client
    assert c.post("/api/renders/sea_a/review", json={"status": "maybe"}).status_code == 422
    assert c.post("/api/renders/bad.name/review", json={"status": "picked"}).status_code == 400


def test_picked_groups_by_slot_and_keeps_loose_picks(client):
    c, review = client
    renders = review.parent / "renders"
    with wave.open(str(renders / "loose.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"\0\0" * 480)
    c.post("/api/renders/sea_b/review", json={"status": "picked"})
    c.post("/api/renders/sea_a/review", json={"status": "rejected"})
    c.post("/api/renders/loose/review", json={"status": "picked"})
    slots = c.get("/api/renders/picked").json()["slots"]
    assert [(s["title"], [x["name"] for x in s["candidates"]]) for s in slots] == [
        ("Ocean bed", ["sea_b"]),
        ("Other picks", ["loose"]),
    ]
    assert slots[0]["candidates"][0]["description"] == "near"
