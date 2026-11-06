"""Non-destructive projects: sources are only ever read, renders go to the render folder."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..config import config
from .analyze import analyze
from .effects import Effect, Gain, Graph
from .ffmpeg import AudioError, binary, probe, run

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


def check_name(name: str) -> str:
    if not NAME_RE.match(name):
        raise AudioError(
            f"Invalid name '{name}': use letters, digits, '-' and '_' (max 80, no path)."
        )
    return name


class Source(BaseModel):
    """Exactly one of sound_id (a downloaded Freesound sound), render (an earlier render of
    this server, by name) or path (a file under data/ or an SFX_READ_ROOTS folder)."""

    model_config = ConfigDict(extra="forbid")
    sound_id: int | None = Field(None, ge=1)
    render: str | None = None
    path: str | None = None

    @model_validator(mode="after")
    def _one(self) -> Source:
        if sum(v is not None for v in (self.sound_id, self.render, self.path)) != 1:
            raise ValueError("A source needs exactly one of sound_id, render or path.")
        return self


class Repeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int = Field(2, ge=1, le=64)
    every_ms: float = Field(ge=1, le=600000, description="Start-to-start spacing of repeats.")


class Layer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field("", max_length=80, description="A label for talking about the layer.")
    source: Source
    offset_ms: float = Field(0, ge=0, le=600000, description="When the layer starts in the mix.")
    gain_db: float = Field(0, ge=-60, le=24)
    effects: list[Effect] = Field(default_factory=list, description="Applied in order.")
    repeat: Repeat | None = None
    mute: bool = False


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(description="Project and output name: letters, digits, '-', '_'.")
    layers: list[Layer] = Field(min_length=1, max_length=64)
    master: list[Effect] = Field(default_factory=list, description="Effects on the summed mix.")
    sample_rate: int = Field(48000, ge=8000, le=192000)
    channels: int = Field(2, ge=1, le=2)
    bit_depth: int = Field(24, description="16 or 24 (PCM WAV).")
    normalize_peak_db: float | None = Field(
        -1.0, ge=-30, le=0, description="Scale the result so its peak sits here; null keeps levels."
    )

    @model_validator(mode="after")
    def _valid(self) -> Project:
        check_name(self.name)
        if self.bit_depth not in (16, 24):
            raise ValueError("bit_depth must be 16 or 24")
        return self


def _inside(path: Path, root: str) -> bool:
    p = os.path.normcase(str(path))
    r = os.path.normcase(str(Path(root).resolve()))
    try:
        return os.path.commonpath([p, r]) == r
    except ValueError:
        return False


def resolve_source(src: Source) -> str:
    if src.sound_id is not None:
        from ..deps import get_cache

        sound = get_cache().get_sound(src.sound_id)
        if not sound:
            raise AudioError(
                f"Sound {src.sound_id} is not downloaded. "
                f"Call sfx_search(operation='download', sound_id={src.sound_id}) first."
            )
        path = Path(sound["local_path"]).resolve()
    elif src.render is not None:
        path = (Path(config.SFX_RENDER_PATH) / f"{check_name(src.render)}.wav").resolve()
    else:
        path = Path(src.path).resolve()
        roots = [config.data_root, *config.SFX_READ_ROOTS]
        if not any(_inside(path, r) for r in roots):
            raise AudioError(
                f"{src.path} is outside the readable folders ({', '.join(roots)}). "
                "Add its folder to SFX_READ_ROOTS."
            )
    if not path.is_file():
        raise AudioError(f"Source file not found: {path}")
    return str(path)


def project_path(name: str) -> Path:
    return Path(config.SFX_PROJECT_PATH) / f"{check_name(name)}.json"


def render_path(name: str) -> Path:
    return Path(config.SFX_RENDER_PATH) / f"{check_name(name)}.wav"


def save_project(project: Project) -> Path:
    path = project_path(project.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(project.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    return path


def load_project(name: str) -> Project:
    path = project_path(name)
    if not path.is_file():
        raise AudioError(f"No project named '{name}'.")
    return Project.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _build(project: Project, inputs: list[str]) -> tuple[Graph, str]:
    g = Graph(project.sample_rate, project.channels)
    layout = "mono" if project.channels == 1 else "stereo"
    mixed: list[str] = []
    for index, layer in enumerate(x for x in project.layers if not x.mute):
        node = g.chain(
            f"{index}:a",
            f"aresample={project.sample_rate},aformat=sample_fmts=fltp:channel_layouts={layout}",
        )
        for effect in layer.effects:
            node = effect.build(g, node)
        if layer.gain_db:
            node = Gain(type="gain", db=layer.gain_db).build(g, node)
        starts = [layer.offset_ms]
        if layer.repeat:
            starts = [layer.offset_ms + i * layer.repeat.every_ms for i in range(layer.repeat.count)]
        copies = [node] if len(starts) == 1 else g.add([node], f"asplit={len(starts)}", len(starts))
        for copy, start in zip(copies, starts):
            mixed.append(g.chain(copy, f"adelay={start:.3f}:all=1") if start else copy)
    if not mixed:
        raise AudioError("Every layer is muted.")
    out = mixed[0]
    if len(mixed) > 1:
        out = g.add(mixed, f"amix=inputs={len(mixed)}:duration=longest:normalize=0")[0]
    for effect in project.master:
        out = effect.build(g, out)
    return g, out


def render(project: Project) -> dict:
    """Render a project to data/renders/<name>.wav, atomically. Returns path + analysis."""
    out_path = render_path(project.name)
    active = [layer for layer in project.layers if not layer.mute]
    if any(layer.source.render == project.name for layer in active):
        raise AudioError("A project cannot use its own render as a source; pick a new name.")
    inputs = [resolve_source(layer.source) for layer in active]
    warnings = []
    for path in inputs:
        info = probe(path)
        if info["duration_s"] > config.SFX_MAX_SOURCE_SECONDS:
            raise AudioError(
                f"{path} is {info['duration_s']:.0f}s, over SFX_MAX_SOURCE_SECONDS="
                f"{config.SFX_MAX_SOURCE_SECONDS:.0f}. Trim it first or raise the limit."
            )
    g, out = _build(project, inputs)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    codec = "pcm_s24le" if project.bit_depth == 24 else "pcm_s16le"
    fd, tmp = tempfile.mkstemp(prefix=".partial-", suffix=".wav", dir=out_path.parent)
    os.close(fd)
    try:
        args = [binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-v", "error"]
        for path in inputs:
            args += ["-i", path]
        args += [
            "-filter_complex",
            g.render(),
            "-map",
            f"[{out}]",
            "-ar",
            str(project.sample_rate),
            "-ac",
            str(project.channels),
            "-c:a",
            codec,
            "-bitexact",
            tmp,
        ]
        run(args)
        stats = analyze(tmp)
        if project.normalize_peak_db is not None and stats["peak_db"] is not None:
            gain = project.normalize_peak_db - stats["peak_db"]
            if abs(gain) > 0.01:
                fd, tmp2 = tempfile.mkstemp(prefix=".partial-", suffix=".wav", dir=out_path.parent)
                os.close(fd)
                try:
                    run(
                        [binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-v", "error",
                         "-i", tmp, "-af", f"volume={gain:.4f}dB", "-c:a", codec,
                         "-bitexact", tmp2]
                    )
                    os.replace(tmp2, tmp)
                finally:
                    if os.path.exists(tmp2):
                        os.remove(tmp2)
                stats = analyze(tmp)
        os.replace(tmp, out_path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    stats["path"] = str(out_path)
    if stats["peak_db"] is not None and stats["peak_db"] > -0.1:
        warnings.append("Peak at 0 dBFS: the render probably clips. Lower gains or add a limiter.")
    if stats.get("leading_silence_s", 0) > 0.05:
        warnings.append(f"{stats['leading_silence_s']:.2f}s of silence at the start.")
    stats["warnings"] = warnings + stats.get("warnings", [])
    save_project(project)
    return stats
