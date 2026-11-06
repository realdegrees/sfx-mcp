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
    assert saved == {"sea_a": {"status": "picked", "note": ""}}
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


def test_modify_needs_a_note(client):
    c, review = client
    assert c.post("/api/renders/sea_a/review", json={"status": "modify"}).status_code == 422
    assert (
        c.post(
            "/api/renders/sea_a/review", json={"status": "modify", "note": "right ear only"}
        ).status_code
        == 200
    )
    saved = json.loads((review / "reviews.json").read_text(encoding="utf-8"))
    assert saved["sea_a"] == {"status": "modify", "note": "right ear only"}


def test_pick_remaining_skips_decided_candidates(client):
    c, review = client
    c.post("/api/renders/sea_a/review", json={"status": "rejected"})
    assert c.post("/api/renders/pick-remaining", json={"slot": "ocean"}).json()["picked"] == [
        "sea_b"
    ]
    saved = json.loads((review / "reviews.json").read_text(encoding="utf-8"))
    assert saved["sea_a"]["status"] == "rejected"
    assert saved["sea_b"]["status"] == "picked"
    assert c.post("/api/renders/pick-remaining", json={"slot": "wind"}).json()["picked"] == []


def test_submission_lists_counts_and_modify_notes(client):
    c, review = client
    c.post("/api/renders/sea_a/review", json={"status": "modify", "note": "too loud"})
    sub = c.post("/api/renders/submission").json()["submission"]
    assert sub["status"] == "waiting"
    assert sub["counts"] == {"picked": 0, "rejected": 0, "modify": 1, "pending": 1}
    assert sub["modify"] == [{"name": "sea_a", "slot": "Ocean bed", "note": "too loud"}]
    on_disk = json.loads((review / "submission.json").read_text(encoding="utf-8"))
    assert on_disk == c.get("/api/renders/submission").json()["submission"]


def test_archived_round_leaves_the_board_but_keeps_its_picks(client):
    c, review = client
    c.post("/api/renders/sea_a/review", json={"status": "picked"})
    (review / "rounds").mkdir()
    (review / "board.json").rename(review / "rounds" / "beds.json")
    (review / "board.json").write_text(
        json.dumps(
            {
                "id": "calls",
                "title": "Calls",
                "slots": [{"key": "gull", "title": "Gull", "candidates": [{"render": "sea_b"}]}],
            }
        ),
        encoding="utf-8",
    )
    board = c.get("/api/renders/board").json()
    assert board["id"] == "calls"
    assert [x["name"] for s in board["slots"] for x in s["candidates"]] == ["sea_b"]
    picked = c.get("/api/renders/picked").json()["slots"]
    assert [(s["title"], s["round"], [x["name"] for x in s["candidates"]]) for s in picked] == [
        ("Ocean bed", "Beds", ["sea_a"])
    ]
    assert c.post("/api/renders/submission").json()["submission"]["round"] == "calls"
