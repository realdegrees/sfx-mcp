from __future__ import annotations

import asyncio
import logging
import random
from typing import Annotated, Literal

from pydantic import Field

from ..audio.analyze import analyze, compare
from ..audio.effects import Effect, HighShelf, Pitch
from ..audio.ffmpeg import AudioError
from ..audio.guide import lookup
from ..audio.project import (
    Layer,
    Project,
    Source,
    check_name,
    load_project,
    project_path,
    render,
    render_path,
    resolve_source,
    save_project,
)
from ..server import mcp

logger = logging.getLogger("sfx-mcp")


def _fail(e: Exception) -> dict:
    logger.warning("audio tool error: %s", e)
    return {"success": False, "error": str(e)}


async def _guarded(fn, *args):
    try:
        return await asyncio.to_thread(fn, *args)
    except (AudioError, ValueError, OSError) as e:
        return _fail(e)


@mcp.tool(annotations={"readOnlyHint": True})
async def audio_guide(
    topic: Annotated[
        str | None,
        Field(
            description="The words of the request ('deeper and less harsh', 'more magical'), "
            "a category ('impact', 'ambience', 'ui', 'footsteps', 'layering') or a section "
            "title. Omit for the list of sections and the workflow."
        ),
    ] = None,
) -> dict:
    """Sound-design rules for game SFX: how descriptive words ("heavier", "less harsh",
    "distant", "magical") translate into concrete effects and parameters of this server, how to
    layer sounds, and recipes per category (impacts, whooshes, magic, UI, footsteps, creatures,
    ambience loops, game delivery). Read the matching sections before planning any edit."""
    return {"success": True, **lookup(topic)}


@mcp.tool(annotations={"readOnlyHint": True})
async def audio_inspect(
    source: Source,
    compare_with: Annotated[
        Source | None,
        Field(description="Another sound; the result adds the differences (source minus this)."),
    ] = None,
) -> dict:
    """Measure a sound: duration, sample rate, channels, peak and RMS level (dBFS), crest_db
    (peak minus RMS: punch), integrated loudness (LUFS), spectral centroid and rolloff (Hz:
    brightness), and silence at the start and end. With compare_with, also returns
    the differences, to check an edit moved things the intended way. Numbers describe the
    signal, not whether it sounds good."""

    def work():
        a = analyze(resolve_source(source))
        out = {"success": True, "analysis": a}
        if compare_with:
            b = analyze(resolve_source(compare_with))
            out["compare_with"] = b
            out["difference"] = compare(b, a)
        return out

    return await _guarded(work)


@mcp.tool
async def audio_process(
    name: Annotated[str, Field(description="Output name (letters, digits, '-', '_').")],
    source: Source,
    effects: Annotated[list[Effect], Field(description="Effect chain, applied in order.")],
    channels: Annotated[int, Field(ge=1, le=2, description="1 for 3D game sounds.")] = 2,
    sample_rate: Annotated[int, Field(ge=8000, le=192000)] = 48000,
    normalize_peak_db: Annotated[float | None, Field(ge=-30, le=0)] = -1.0,
) -> dict:
    """Run one sound through an effect chain and render data/renders/<name>.wav. This is a
    one-layer project, saved as such, so it can be reopened and edited with audio_project /
    audio_render. The source file is never modified. Read audio_guide first."""
    project = Project(
        name=name,
        layers=[Layer(name="main", source=source, effects=effects)],
        channels=channels,
        sample_rate=sample_rate,
        normalize_peak_db=normalize_peak_db,
    )
    return await _guarded(lambda: {"success": True, "render": render(project)})


@mcp.tool
async def audio_render(project: Project) -> dict:
    """Render a multi-layer project to data/renders/<name>.wav and save it as
    data/projects/<name>.json. Each layer: a source (sound_id of a downloaded Freesound sound,
    an earlier render by name, or a path), offset_ms on the timeline, gain_db, its own effect
    chain, optional repeat. master effects run on the mix; normalize_peak_db sets the final
    peak. To revise, get the saved project with audio_project, change it, render again (same
    name overwrites that render; a new name keeps both). Sources are never modified."""
    return await _guarded(lambda: {"success": True, "render": render(project)})


@mcp.tool
async def audio_project(
    operation: Literal["list", "get", "copy", "delete"],
    name: Annotated[str | None, Field(description="Project name. Required for get, copy, delete.")] = None,
    new_name: Annotated[str | None, Field(description="Required for copy.")] = None,
) -> dict:
    """Manage saved projects. list: names with their render status. get: the project JSON, to
    edit and pass back to audio_render. copy: duplicate under new_name (to branch a candidate).
    delete: remove the project and its render."""

    def work():
        if operation == "list":
            folder = project_path("x").parent
            names = sorted(p.stem for p in folder.glob("*.json")) if folder.is_dir() else []
            return {
                "success": True,
                "projects": [{"name": n, "rendered": render_path(n).is_file()} for n in names],
            }
        if not name:
            raise AudioError("name is required")
        if operation == "get":
            return {"success": True, "project": load_project(name).model_dump(exclude_none=True)}
        if operation == "copy":
            if not new_name:
                raise AudioError("new_name is required for copy")
            project = load_project(name).model_copy(update={"name": check_name(new_name)})
            save_project(project)
            return {"success": True, "project": project.model_dump(exclude_none=True)}
        project_path(name).unlink(missing_ok=True)
        render_path(name).unlink(missing_ok=True)
        return {"success": True, "deleted": name}

    return await _guarded(work)


@mcp.tool
async def audio_variations(
    project: Annotated[str, Field(description="Name of a saved project to vary.")],
    count: Annotated[int, Field(ge=1, le=16)] = 4,
    seed: Annotated[int, Field(ge=0)] = 1,
    pitch_semitones: Annotated[
        float, Field(ge=0, le=12, description="Max tape-style pitch change per layer, +-.")
    ] = 1.0,
    gain_db: Annotated[float, Field(ge=0, le=12, description="Max level change per layer, +-.")] = 1.5,
    timing_ms: Annotated[
        float, Field(ge=0, le=500, description="Max shift of each non-zero layer offset, +-.")
    ] = 10.0,
    tone_db: Annotated[
        float, Field(ge=0, le=12, description="Max high-shelf change at 4 kHz per layer, +-.")
    ] = 0.0,
) -> dict:
    """Render <project>_v01 to _vNN: the project with seeded random pitch, level, timing and
    tone per layer, for pools of footsteps, impacts or calls that must not repeat audibly. The
    same seed gives the same set. See audio_guide('variations') for ranges per category."""

    def work():
        base = load_project(project)
        results = []
        for i in range(1, count + 1):
            rng = random.Random(seed * 1009 + i)
            layers = []
            for layer in base.layers:
                extra: list[Effect] = []
                if pitch_semitones:
                    extra.append(
                        Pitch(type="pitch", semitones=round(rng.uniform(-pitch_semitones, pitch_semitones), 3),
                              preserve_duration=False)
                    )
                if tone_db:
                    extra.append(
                        HighShelf(type="high_shelf", freq_hz=4000,
                                  gain_db=round(rng.uniform(-tone_db, tone_db), 2))
                    )
                offset = layer.offset_ms
                if offset and timing_ms:
                    offset = max(0.0, offset + rng.uniform(-timing_ms, timing_ms))
                layers.append(
                    layer.model_copy(
                        update={
                            "offset_ms": round(offset, 2),
                            "gain_db": round(layer.gain_db + rng.uniform(-gain_db, gain_db), 2),
                            "effects": extra + list(layer.effects),
                        }
                    )
                )
            variant = base.model_copy(update={"name": f"{base.name}_v{i:02d}", "layers": layers})
            r = render(variant)
            results.append({"name": variant.name, "path": r["path"], "peak_db": r["peak_db"],
                            "duration_s": r["duration_s"]})
        return {"success": True, "variations": results}

    return await _guarded(work)
