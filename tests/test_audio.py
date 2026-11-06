"""Audio engine tests on generated test tones. Run with ffmpeg on PATH or FFMPEG_DIR set."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sfx_mcp.audio import ffmpeg
from sfx_mcp.audio.analyze import analyze
from sfx_mcp.audio.ffmpeg import AudioError
from sfx_mcp.audio.guide import lookup
from sfx_mcp.audio.project import (
    Project,
    Source,
    load_project,
    render,
    resolve_source,
    save_project,
)
from sfx_mcp.config import config

try:
    ffmpeg.binary("ffmpeg")
    HAVE_FFMPEG = True
except AudioError:
    HAVE_FFMPEG = False

needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not available")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SFX_RENDER_PATH", str(tmp_path / "renders"))
    monkeypatch.setattr(config, "SFX_PROJECT_PATH", str(tmp_path / "projects"))
    monkeypatch.setattr(config, "SFX_READ_ROOTS", [str(tmp_path / "src")])
    (tmp_path / "src").mkdir()
    return tmp_path


def tone(workspace, name: str, freq: float, seconds: float) -> str:
    path = workspace / "src" / f"{name}.wav"
    ffmpeg.run(
        [ffmpeg.binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"sine=frequency={freq}:duration={seconds}:sample_rate=48000",
         "-c:a", "pcm_s16le", str(path)]
    )
    return str(path)


def project(name: str, layers: list[dict], **kw) -> Project:
    return Project.model_validate({"name": name, "layers": layers, **kw})


@needs_ffmpeg
def test_layer_offsets_place_sounds_on_the_timeline(workspace):
    src = tone(workspace, "beep", 1000, 0.1)
    out = render(project("offsets", [{"source": {"path": src}, "offset_ms": 500}]))
    assert out["leading_silence_s"] == pytest.approx(0.5, abs=0.02)
    assert out["duration_s"] == pytest.approx(0.6, abs=0.02)


@needs_ffmpeg
def test_repeat_spaces_copies(workspace):
    src = tone(workspace, "beep", 1000, 0.1)
    out = render(
        project("repeat", [{"source": {"path": src}, "repeat": {"count": 3, "every_ms": 200}}])
    )
    assert out["duration_s"] == pytest.approx(0.5, abs=0.02)


@needs_ffmpeg
def test_tape_pitch_down_an_octave_halves_frequency_and_doubles_length(workspace):
    src = tone(workspace, "a", 1000, 0.5)
    out = render(
        project("tape", [{"source": {"path": src},
                          "effects": [{"type": "pitch", "semitones": -12, "preserve_duration": False}]}])
    )
    assert out["duration_s"] == pytest.approx(1.0, abs=0.03)
    assert out["spectral_centroid_hz"] == pytest.approx(500, rel=0.08)


@needs_ffmpeg
def test_rubberband_pitch_keeps_duration(workspace):
    src = tone(workspace, "a", 1000, 0.5)
    out = render(
        project("rb", [{"source": {"path": src}, "effects": [{"type": "pitch", "semitones": 12}]}])
    )
    assert out["duration_s"] == pytest.approx(0.5, abs=0.05)
    assert out["spectral_centroid_hz"] == pytest.approx(2000, rel=0.08)


@needs_ffmpeg
def test_speed_preserving_pitch_changes_length_only(workspace):
    src = tone(workspace, "a", 1000, 1.0)
    out = render(
        project("speed", [{"source": {"path": src}, "effects": [{"type": "speed", "factor": 2}]}])
    )
    assert out["duration_s"] == pytest.approx(0.5, abs=0.05)
    assert out["spectral_centroid_hz"] == pytest.approx(1000, rel=0.08)


@needs_ffmpeg
def test_lowpass_darkens(workspace):
    low = tone(workspace, "low", 300, 0.5)
    high = tone(workspace, "high", 6000, 0.5)
    mix = [{"source": {"path": low}}, {"source": {"path": high}}]
    bright = render(project("bright", mix))
    dark = render(project("dark", mix, master=[{"type": "lowpass", "freq_hz": 1000, "slope_db_per_oct": 48}]))
    assert dark["spectral_centroid_hz"] < bright["spectral_centroid_hz"] - 1500


@needs_ffmpeg
def test_reverb_adds_its_tail_and_is_reproducible(workspace):
    src = tone(workspace, "a", 800, 0.2)
    p = project("verb", [{"source": {"path": src}, "effects": [{"type": "reverb", "decay_s": 1.0}]}])
    first = render(p)
    assert first["duration_s"] == pytest.approx(1.2, abs=0.05)
    bytes_a = (workspace / "renders" / "verb.wav").read_bytes()
    render(p)
    assert (workspace / "renders" / "verb.wav").read_bytes() == bytes_a


@needs_ffmpeg
def test_make_loop_shortens_by_crossfade_and_joins_end_to_start(workspace):
    src = tone(workspace, "bed", 440, 4.0)
    out = render(
        project("loop", [{"source": {"path": src}, "effects": [{"type": "make_loop", "crossfade_ms": 1000}]}])
    )
    assert out["duration_s"] == pytest.approx(3.0, abs=0.02)


@needs_ffmpeg
def test_effect_order_matters(workspace):
    src = tone(workspace, "a", 1000, 0.3)
    pad_first = render(project("fp", [{"source": {"path": src}, "effects": [
        {"type": "pad", "after_ms": 300}, {"type": "trim_silence", "start": False}]}]))
    pad_last = render(project("pf", [{"source": {"path": src}, "effects": [
        {"type": "trim_silence", "start": False}, {"type": "pad", "after_ms": 300}]}]))
    assert pad_first["duration_s"] == pytest.approx(0.3, abs=0.03)
    assert pad_last["duration_s"] == pytest.approx(0.6, abs=0.03)


@needs_ffmpeg
def test_normalize_sets_peak(workspace):
    src = tone(workspace, "a", 1000, 0.3)
    out = render(project("norm", [{"source": {"path": src}, "gain_db": -20}], normalize_peak_db=-3))
    assert out["peak_db"] == pytest.approx(-3, abs=0.1)
    raw = render(project("raw", [{"source": {"path": src}, "gain_db": -20}], normalize_peak_db=None))
    assert raw["peak_db"] < -15


@needs_ffmpeg
def test_render_can_layer_an_earlier_render_but_not_itself(workspace):
    src = tone(workspace, "a", 1000, 0.2)
    render(project("base", [{"source": {"path": src}}]))
    out = render(project("stacked", [{"source": {"render": "base"}, "offset_ms": 100}]))
    assert out["duration_s"] == pytest.approx(0.3, abs=0.02)
    with pytest.raises(AudioError):
        render(project("base", [{"source": {"render": "base"}}]))


@needs_ffmpeg
def test_sources_are_never_modified(workspace):
    src = tone(workspace, "a", 1000, 0.2)
    before = open(src, "rb").read()
    render(project("touch", [{"source": {"path": src}, "effects": [{"type": "reverse"}]}]))
    assert open(src, "rb").read() == before


@needs_ffmpeg
def test_analyze_reports_level_and_silence(workspace):
    src = tone(workspace, "a", 1000, 0.5)
    out = render(project("quiet", [{"source": {"path": src}, "effects": [{"type": "pad", "before_ms": 250}]}],
                         normalize_peak_db=-6))
    info = analyze(out["path"])
    assert info["peak_db"] == pytest.approx(-6, abs=0.2)
    assert info["leading_silence_s"] == pytest.approx(0.25, abs=0.02)
    assert info["channels"] == 2 and info["sample_rate"] == 48000


def test_project_round_trip(workspace):
    p = project("trip", [{"source": {"sound_id": 5}, "offset_ms": 30, "gain_db": -3,
                          "effects": [{"type": "eq", "freq_hz": 300, "gain_db": -4, "q": 2}]}],
                master=[{"type": "limiter", "ceiling_db": -1}])
    save_project(p)
    assert load_project("trip") == p


def test_parameter_ranges_are_enforced():
    with pytest.raises(ValidationError):
        project("x", [{"source": {"sound_id": 1}, "effects": [{"type": "pitch", "semitones": 99}]}])
    with pytest.raises(ValidationError):
        project("x", [{"source": {"sound_id": 1}, "effects": [{"type": "nope"}]}])
    with pytest.raises(ValidationError):
        project("x", [{"source": {"sound_id": 1}, "effects": [{"type": "gain", "db": 1, "extra": 2}]}])


def test_names_cannot_escape_the_render_folder():
    for bad in ["../evil", "a/b", "", "x" * 81, "C:evil"]:
        with pytest.raises((ValidationError, AudioError)):
            project(bad, [{"source": {"sound_id": 1}}])


def test_source_needs_exactly_one_kind():
    with pytest.raises(ValidationError):
        Source(sound_id=1, path="a.wav")
    with pytest.raises(ValidationError):
        Source()


def test_paths_outside_read_roots_are_refused(workspace, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "a.wav"
    outside.write_bytes(b"RIFF")
    with pytest.raises(AudioError, match="outside the readable folders"):
        resolve_source(Source(path=str(outside)))
    sneaky = workspace / "src" / ".." / ".." / outside.parent.name / "a.wav"
    with pytest.raises(AudioError):
        resolve_source(Source(path=str(sneaky)))


def test_missing_ffmpeg_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "FFMPEG_DIR", str(tmp_path))
    ffmpeg.binary.cache_clear()
    try:
        with pytest.raises(AudioError, match="not found"):
            ffmpeg.binary("ffmpeg")
    finally:
        ffmpeg.binary.cache_clear()


def test_guide_maps_words_to_sections():
    assert lookup("make it less harsh")["matches"][0]["title"].startswith("Less harsh")
    assert lookup("deeper and heavier")["matches"][0]["title"].startswith("Deeper")
    assert any(m["title"].startswith("Ambience") for m in lookup("seamless sea loop")["matches"])
    assert "Workflow" in lookup(None)["sections"]
