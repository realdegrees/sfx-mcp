"""Typed effect catalogue. Each effect validates its own parameters and emits ffmpeg filters.

Agents never pass filter strings; they pick an effect by `type` and fill named, ranged fields.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from .ffmpeg import require_filter


def _lin(db: float) -> float:
    return 10 ** (db / 20)


class Graph:
    """Builds an ffmpeg filter_complex out of labelled chains."""

    def __init__(self, sample_rate: int, channels: int) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.chains: list[str] = []
        self._n = 0

    def label(self) -> str:
        self._n += 1
        return f"n{self._n}"

    def add(self, inputs: list[str], filters: str, outputs: int = 1) -> list[str]:
        outs = [self.label() for _ in range(outputs)]
        self.chains.append(
            "".join(f"[{i}]" for i in inputs) + filters + "".join(f"[{o}]" for o in outs)
        )
        return outs

    def chain(self, inp: str, filters: str) -> str:
        return self.add([inp], filters)[0]

    def render(self) -> str:
        return ";".join(self.chains)


class _Effect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def build(self, g: Graph, inp: str) -> str:
        raise NotImplementedError


class Gain(_Effect):
    """Change level. +6 dB is roughly twice the amplitude."""

    type: Literal["gain"]
    db: float = Field(ge=-60, le=30, description="Gain in dB.")

    def build(self, g, inp):
        return g.chain(inp, f"volume={self.db}dB")


class Trim(_Effect):
    """Keep only part of the sound."""

    type: Literal["trim"]
    start_ms: float = Field(0, ge=0, description="Start of the kept part, ms.")
    end_ms: float | None = Field(None, gt=0, description="End of the kept part, ms. Omit for the end.")

    def build(self, g, inp):
        end = f":end={self.end_ms / 1000}" if self.end_ms else ""
        return g.chain(inp, f"atrim=start={self.start_ms / 1000}{end},asetpts=PTS-STARTPTS")


_CURVES = {"linear": "tri", "smooth": "qsin", "exponential": "exp", "logarithmic": "log"}


class Fade(_Effect):
    """Fade in and/or out. Exponential fade-outs sound natural on decays."""

    type: Literal["fade"]
    in_ms: float = Field(0, ge=0, le=60000)
    out_ms: float = Field(0, ge=0, le=60000)
    curve: Literal["linear", "smooth", "exponential", "logarithmic"] = "smooth"

    def build(self, g, inp):
        c = _CURVES[self.curve]
        out = inp
        if self.in_ms:
            out = g.chain(out, f"afade=t=in:d={self.in_ms / 1000}:curve={c}")
        if self.out_ms:
            # Reversing lets the fade sit at the true end without knowing the duration.
            out = g.chain(out, f"areverse,afade=t=in:d={self.out_ms / 1000}:curve={c},areverse")
        return out


class Pitch(_Effect):
    """Shift pitch in semitones. preserve_duration=false is the tape-style shift: lower is also
    slower and longer, which is the classic way to make a sound bigger and heavier."""

    type: Literal["pitch"]
    semitones: float = Field(ge=-36, le=36)
    preserve_duration: bool = True

    def build(self, g, inp):
        ratio = 2 ** (self.semitones / 12)
        if self.preserve_duration:
            require_filter("rubberband")
            return g.chain(inp, f"rubberband=pitch={ratio:.6f}:transients=mixed:pitchq=quality")
        return g.chain(inp, f"asetrate={g.sample_rate * ratio:.3f},aresample={g.sample_rate}")


class Speed(_Effect):
    """Change speed. factor 2 = twice as fast (half the length). To fit a length:
    factor = current_duration / target_duration. preserve_pitch=false changes pitch with it."""

    type: Literal["speed"]
    factor: float = Field(ge=0.1, le=10)
    preserve_pitch: bool = True

    def build(self, g, inp):
        if self.preserve_pitch:
            require_filter("rubberband")
            return g.chain(inp, f"rubberband=tempo={self.factor:.6f}:transients=mixed")
        return g.chain(inp, f"asetrate={g.sample_rate * self.factor:.3f},aresample={g.sample_rate}")


class Eq(_Effect):
    """Peaking EQ band. Cut narrow (q 4 to 10) to remove a resonance, boost wide (q 0.5 to 1.5)."""

    type: Literal["eq"]
    freq_hz: float = Field(ge=20, le=20000)
    gain_db: float = Field(ge=-30, le=24)
    q: float = Field(1.0, ge=0.1, le=20)

    def build(self, g, inp):
        return g.chain(inp, f"equalizer=f={self.freq_hz}:t=q:w={self.q}:g={self.gain_db}")


class LowShelf(_Effect):
    """Raise or lower everything below freq_hz."""

    type: Literal["low_shelf"]
    freq_hz: float = Field(ge=20, le=2000)
    gain_db: float = Field(ge=-30, le=24)

    def build(self, g, inp):
        return g.chain(inp, f"lowshelf=f={self.freq_hz}:g={self.gain_db}")


class HighShelf(_Effect):
    """Raise or lower everything above freq_hz."""

    type: Literal["high_shelf"]
    freq_hz: float = Field(ge=500, le=20000)
    gain_db: float = Field(ge=-30, le=24)

    def build(self, g, inp):
        return g.chain(inp, f"highshelf=f={self.freq_hz}:g={self.gain_db}")


def _repeat_filter(name: str, freq: float, slope: int) -> str:
    if slope == 6:
        return f"{name}=f={freq}:p=1"
    return ",".join([f"{name}=f={freq}:p=2"] * (slope // 12))


class Lowpass(_Effect):
    """Remove content above freq_hz. Darker, more distant, muffled, behind a wall."""

    type: Literal["lowpass"]
    freq_hz: float = Field(ge=20, le=20000)
    slope_db_per_oct: Literal[6, 12, 24, 48] = 12

    def build(self, g, inp):
        return g.chain(inp, _repeat_filter("lowpass", self.freq_hz, self.slope_db_per_oct))


class Highpass(_Effect):
    """Remove content below freq_hz. Thinner, smaller, cleans rumble and mud out of a layer."""

    type: Literal["highpass"]
    freq_hz: float = Field(ge=10, le=20000)
    slope_db_per_oct: Literal[6, 12, 24, 48] = 12

    def build(self, g, inp):
        return g.chain(inp, _repeat_filter("highpass", self.freq_hz, self.slope_db_per_oct))


class Bandpass(_Effect):
    """Keep a band around freq_hz. Telephone, radio, small speaker, distant tonal layer."""

    type: Literal["bandpass"]
    freq_hz: float = Field(ge=20, le=20000)
    q: float = Field(1.0, ge=0.1, le=20)

    def build(self, g, inp):
        return g.chain(inp, f"bandpass=f={self.freq_hz}:t=q:w={self.q}")


class Notch(_Effect):
    """Remove a narrow band (a whistle, hum, ringing resonance)."""

    type: Literal["notch"]
    freq_hz: float = Field(ge=20, le=20000)
    q: float = Field(8.0, ge=0.5, le=50)

    def build(self, g, inp):
        return g.chain(inp, f"bandreject=f={self.freq_hz}:t=q:w={self.q}")


class Reverb(_Effect):
    """Convolution reverb with a generated decaying-noise impulse. Adds a tail of decay_s.
    Small room 0.3 to 0.8 s, hall 1.5 to 3 s, cave or cathedral 3 to 8 s."""

    type: Literal["reverb"]
    decay_s: float = Field(1.2, ge=0.05, le=12)
    wet: float = Field(0.3, ge=0, le=1, description="Reverb level, 0 dry to 1 fully wet.")
    damping_hz: float = Field(
        7000, ge=500, le=20000, description="High cut on the tail; lower is darker and softer."
    )
    predelay_ms: float = Field(0, ge=0, le=300)
    seed: int = Field(1, ge=0, le=1_000_000, description="Seed of the impulse; fixed = repeatable.")

    def build(self, g, inp):
        require_filter("afir")
        noises = []
        for ch in range(g.channels):
            noises.append(
                g.add(
                    [],
                    f"anoisesrc=d={self.decay_s}:c=white:r={g.sample_rate}:a=0.5"
                    f":seed={self.seed * 7 + ch},afade=t=out:st=0:d={self.decay_s}:curve=exp,"
                    f"lowpass=f={self.damping_hz}",
                )[0]
            )
        ir = noises[0] if g.channels == 1 else g.add(noises, f"amerge=inputs={g.channels}")[0]
        if self.predelay_ms:
            ir = g.chain(ir, f"adelay={self.predelay_ms}:all=1")
        padded = g.chain(inp, f"apad=pad_dur={self.decay_s + self.predelay_ms / 1000}")
        return g.add(
            [padded, ir],
            f"afir=dry={1 - self.wet * 0.5:.3f}:wet={self.wet:.3f}:irnorm=1",
        )[0]


class Echo(_Effect):
    """Discrete repeats. Slapback 60 to 120 ms with one repeat; canyon 300 to 600 ms."""

    type: Literal["echo"]
    delay_ms: float = Field(250, ge=10, le=3000)
    feedback: float = Field(0.4, ge=0, le=0.9, description="Level of each repeat vs the last.")
    wet: float = Field(0.5, ge=0, le=1)

    def build(self, g, inp):
        taps = []
        level = self.feedback
        while level >= 0.02 and len(taps) < 12:
            taps.append(level)
            level *= self.feedback
        if not taps:
            return inp
        delays = "|".join(str(self.delay_ms * (i + 1)) for i in range(len(taps)))
        decays = "|".join(f"{t * self.wet:.4f}" for t in taps)
        padded = g.chain(inp, f"apad=pad_dur={self.delay_ms * len(taps) / 1000}")
        return g.chain(padded, f"aecho=in_gain=1:out_gain=1:delays={delays}:decays={decays}")


class Compressor(_Effect):
    """Even out level. Slow attack (20 to 50 ms) keeps and emphasises the hit; fast attack
    (0.5 to 5 ms) flattens it. Higher ratio = stronger."""

    type: Literal["compressor"]
    threshold_db: float = Field(-18, ge=-60, le=0)
    ratio: float = Field(4, ge=1, le=20)
    attack_ms: float = Field(10, ge=0.01, le=2000)
    release_ms: float = Field(120, ge=0.01, le=9000)
    makeup_db: float = Field(0, ge=0, le=36)
    knee_db: float = Field(3, ge=0, le=18)

    def build(self, g, inp):
        return g.chain(
            inp,
            f"acompressor=threshold={_lin(self.threshold_db):.6f}:ratio={self.ratio}"
            f":attack={self.attack_ms}:release={self.release_ms}"
            f":makeup={_lin(self.makeup_db):.4f}:knee={_lin(self.knee_db):.4f}",
        )


class Limiter(_Effect):
    """Hard ceiling on peaks."""

    type: Literal["limiter"]
    ceiling_db: float = Field(-1, ge=-30, le=0)

    def build(self, g, inp):
        return g.chain(inp, f"alimiter=limit={_lin(self.ceiling_db):.6f}:level=0:latency=1")


class Saturate(_Effect):
    """Soft-clip distortion. Light drive (3 to 9 dB) adds weight and warmth, heavy (15+) grit."""

    type: Literal["saturate"]
    drive_db: float = Field(6, ge=0, le=36)
    style: Literal["tanh", "atan", "cubic", "hard"] = "tanh"

    def build(self, g, inp):
        return g.chain(
            inp,
            f"volume={self.drive_db}dB,asoftclip=type={self.style},volume={-self.drive_db / 2}dB",
        )


class Chorus(_Effect):
    """Several detuned copies. Thicker, wider, shimmering, more magical."""

    type: Literal["chorus"]
    rate_hz: float = Field(0.5, ge=0.05, le=10)
    depth_ms: float = Field(2.5, ge=0.1, le=10)
    mix: float = Field(0.5, ge=0, le=1)

    def build(self, g, inp):
        r, d, m = self.rate_hz, self.depth_ms, self.mix
        return g.chain(
            inp,
            f"chorus=in_gain={1 - m * 0.4:.3f}:out_gain=0.9:delays=40|55|70"
            f":decays={m * 0.5:.3f}|{m * 0.45:.3f}|{m * 0.4:.3f}"
            f":speeds={r}|{r * 1.37:.3f}|{r * 0.73:.3f}:depths={d}|{d * 1.2:.3f}|{d * 0.8:.3f}",
        )


class Flanger(_Effect):
    """Sweeping comb filter. Jet, whoosh, sci-fi, unstable energy."""

    type: Literal["flanger"]
    delay_ms: float = Field(2, ge=0, le=30)
    depth_ms: float = Field(3, ge=0, le=10)
    rate_hz: float = Field(0.5, ge=0.1, le=10)
    regen: float = Field(30, ge=-95, le=95, description="Feedback percent; high = metallic.")

    def build(self, g, inp):
        return g.chain(
            inp,
            f"flanger=delay={self.delay_ms}:depth={self.depth_ms}"
            f":regen={self.regen}:speed={self.rate_hz}",
        )


class Phaser(_Effect):
    """Sweeping notches. Softer and swirlier than a flanger."""

    type: Literal["phaser"]
    rate_hz: float = Field(0.5, ge=0.1, le=2)
    decay: float = Field(0.4, ge=0, le=0.99)

    def build(self, g, inp):
        return g.chain(inp, f"aphaser=speed={self.rate_hz}:decay={self.decay}")


class Tremolo(_Effect):
    """Volume wobble. Slow = pulsing, fast (15+ Hz) = buzzing, flutter."""

    type: Literal["tremolo"]
    rate_hz: float = Field(5, ge=0.1, le=20000)
    depth: float = Field(0.5, ge=0, le=1)

    def build(self, g, inp):
        return g.chain(inp, f"tremolo=f={self.rate_hz}:d={self.depth}")


class Vibrato(_Effect):
    """Pitch wobble. "Wobble between high and low", warble, unstable, drunk, ghostly."""

    type: Literal["vibrato"]
    rate_hz: float = Field(5, ge=0.1, le=20000)
    depth: float = Field(0.5, ge=0, le=1)

    def build(self, g, inp):
        return g.chain(inp, f"vibrato=f={self.rate_hz}:d={self.depth}")


class Reverse(_Effect):
    """Play backwards. A reversed tail before a hit makes a swell or suck-in."""

    type: Literal["reverse"]

    def build(self, g, inp):
        return g.chain(inp, "areverse")


class Pan(_Effect):
    """Stereo position, -1 left to 1 right (equal power). No effect on mono output."""

    type: Literal["pan"]
    position: float = Field(ge=-1, le=1)

    def build(self, g, inp):
        if g.channels == 1:
            return inp
        angle = (self.position + 1) * math.pi / 4
        left, right = math.cos(angle) * 1.4142, math.sin(angle) * 1.4142
        return g.chain(inp, f"pan=stereo|c0={left:.4f}*c0|c1={right:.4f}*c1")


class StereoWidth(_Effect):
    """0 = mono, 1 = unchanged, up to 2.5 = wider. Keep sub layers narrow."""

    type: Literal["stereo_width"]
    width: float = Field(ge=0, le=2.5)

    def build(self, g, inp):
        if g.channels == 1:
            return inp
        return g.chain(inp, f"extrastereo=m={self.width}:c=0")


class Gate(_Effect):
    """Silence everything below a threshold. Cuts noise between hits, shortens tails."""

    type: Literal["gate"]
    threshold_db: float = Field(-40, ge=-80, le=0)
    ratio: float = Field(10, ge=1, le=9000)
    attack_ms: float = Field(1, ge=0.01, le=9000)
    release_ms: float = Field(80, ge=0.01, le=9000)

    def build(self, g, inp):
        return g.chain(
            inp,
            f"agate=threshold={_lin(self.threshold_db):.6f}:ratio={self.ratio}"
            f":attack={self.attack_ms}:release={self.release_ms}",
        )


class TrimSilence(_Effect):
    """Remove silence from the start and/or end."""

    type: Literal["trim_silence"]
    threshold_db: float = Field(-50, ge=-90, le=-10)
    start: bool = True
    end: bool = True

    def build(self, g, inp):
        f = f"silenceremove=start_periods=1:start_threshold={self.threshold_db}dB"
        out = inp
        if self.start:
            out = g.chain(out, f)
        if self.end:
            out = g.chain(out, f"areverse,{f},areverse")
        return out


class Pad(_Effect):
    """Add silence before and/or after."""

    type: Literal["pad"]
    before_ms: float = Field(0, ge=0, le=60000)
    after_ms: float = Field(0, ge=0, le=60000)

    def build(self, g, inp):
        out = inp
        if self.before_ms:
            out = g.chain(out, f"adelay={self.before_ms}:all=1")
        if self.after_ms:
            out = g.chain(out, f"apad=pad_dur={self.after_ms / 1000}")
        return out


class MakeLoop(_Effect):
    """Make the sound loop seamlessly: its end is crossfaded (equal power) into its start, so the
    result is crossfade_ms shorter and its last sample runs into its first. Put it last in the
    chain (after any reverb or echo tail), and pick a crossfade of 0.5 to 3 s for beds."""

    type: Literal["make_loop"]
    crossfade_ms: float = Field(1500, ge=5, le=30000)

    def build(self, g, inp):
        c = self.crossfade_ms / 1000
        body, head = g.add([inp], "asplit=2", outputs=2)
        body = g.chain(body, f"atrim=start={c},asetpts=PTS-STARTPTS")
        head = g.chain(head, f"atrim=end={c},asetpts=PTS-STARTPTS")
        return g.add([body, head], f"acrossfade=d={c}:c1=qsin:c2=qsin")[0]


Effect = Annotated[
    Union[
        Gain,
        Trim,
        Fade,
        Pitch,
        Speed,
        Eq,
        LowShelf,
        HighShelf,
        Lowpass,
        Highpass,
        Bandpass,
        Notch,
        Reverb,
        Echo,
        Compressor,
        Limiter,
        Saturate,
        Chorus,
        Flanger,
        Phaser,
        Tremolo,
        Vibrato,
        Reverse,
        Pan,
        StereoWidth,
        Gate,
        TrimSilence,
        Pad,
        MakeLoop,
    ],
    Field(discriminator="type"),
]
