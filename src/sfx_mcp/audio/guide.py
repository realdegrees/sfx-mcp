"""Section lookup over design_guide.md."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_GUIDE = Path(__file__).with_name("design_guide.md")


@lru_cache(maxsize=1)
def sections() -> list[dict]:
    text = _GUIDE.read_text(encoding="utf-8")
    out = []
    for block in re.split(r"(?m)^## ", text)[1:]:
        title, _, body = block.partition("\n")
        match = re.match(r"Keywords: (.*)\n", body.lstrip("\n"))
        keywords = {k.strip().lower() for k in match.group(1).split(",")} if match else set()
        out.append({"title": title.strip(), "keywords": keywords, "body": body.strip()})
    return out


def lookup(topic: str | None) -> dict:
    all_sections = sections()
    if not topic:
        return {
            "sections": [s["title"] for s in all_sections],
            "workflow": next(s["body"] for s in all_sections if s["title"] == "Workflow"),
            "hint": "Call again with a topic: the words of the request ('deeper and less harsh'), "
            "a category ('ambience', 'impact', 'ui') or a section title.",
        }
    words = set(re.findall(r"[a-z0-9-]+", topic.lower()))
    phrase = topic.lower().strip()
    scored = []
    for s in all_sections:
        score = 3 * (phrase == s["title"].lower())
        score += sum(1 for k in s["keywords"] if k in words or (" " in k and k in phrase))
        if score:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return {
            "matches": [],
            "sections": [s["title"] for s in all_sections],
            "hint": "No section matched; pick a section title or use more common words.",
        }
    return {
        "matches": [{"title": s["title"], "rules": s["body"]} for _, s in scored[:4]],
        "reminder": "Starting points, not answers: render candidates and let a listener judge.",
    }
