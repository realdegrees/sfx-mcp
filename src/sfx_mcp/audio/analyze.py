"""Measurable properties of a sound. Numbers describe the signal, not whether it sounds good."""

from __future__ import annotations

import os
import re
import tempfile

from .ffmpeg import binary, probe, run

_NUM = r"(-?inf|-?\d+(?:\.\d+)?)"


def _db(value: str | None) -> float | None:
    if value is None or "inf" in value:
        return None
    return round(float(value), 2)


def _last(pattern: str, text: str) -> str | None:
    found = re.findall(pattern, text)
    return found[-1] if found else None


def analyze(path: str) -> dict:
    info = probe(path)
    duration = info["duration_s"]
    fd, spectral_file = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        chain = (
            "astats=metadata=0:measure_perchannel=none:measure_overall=Peak_level+RMS_level,"
            "silencedetect=n=-50dB:d=0.03,"
            # ametadata's file= option is parsed by the filter-graph parser, so escape for it.
            "aspectralstats=win_size=2048:measure=centroid+rolloff,"
            f"ametadata=mode=print:file='{spectral_file.replace(chr(92), '/').replace(':', chr(92) + ':')}'"
        )
        if duration >= 0.4:
            chain += ",ebur128=peak=true"
        err = run(
            [binary("ffmpeg"), "-hide_banner", "-nostdin", "-v", "info", "-i", path,
             "-af", chain, "-f", "null", "-"]
        ).stderr
        with open(spectral_file, encoding="utf-8", errors="replace") as f:
            spectral = f.read()
    finally:
        os.remove(spectral_file)

    centroids = [float(v) for v in re.findall(r"\.centroid=([\d.]+)", spectral)]
    rolloffs = [float(v) for v in re.findall(r"\.rolloff=([\d.]+)", spectral)]
    starts = [float(v) for v in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(v) for v in re.findall(r"silence_end: ([\d.]+)", err)]
    leading = ends[0] if starts and starts[0] <= 0.001 and ends else 0.0
    trailing = duration - starts[-1] if starts and len(starts) > len(ends) else 0.0

    result = {
        **info,
        "peak_db": _db(_last(rf"Peak level dB: {_NUM}", err)),
        "rms_db": _db(_last(rf"RMS level dB: {_NUM}", err)),
        "integrated_lufs": _db(_last(rf"I:\s+{_NUM} LUFS", err)) if duration >= 0.4 else None,
        "loudness_range_lu": _db(_last(rf"LRA:\s+{_NUM} LU", err)) if duration >= 0.4 else None,
        "spectral_centroid_hz": round(sum(centroids) / len(centroids)) if centroids else None,
        "spectral_rolloff_hz": round(sum(rolloffs) / len(rolloffs)) if rolloffs else None,
        "leading_silence_s": round(leading, 3),
        "trailing_silence_s": round(max(trailing, 0.0), 3),
    }
    # Peak minus RMS: high = punchy and transient, low = dense, compressed or sustained.
    result["crest_db"] = (
        round(result["peak_db"] - result["rms_db"], 2)
        if result["peak_db"] is not None and result["rms_db"] is not None else None
    )
    warnings = []
    if result["peak_db"] is None:
        warnings.append("The file is silent.")
    elif result["peak_db"] > -0.1:
        warnings.append("Peak at 0 dBFS: likely clipped.")
    result["warnings"] = warnings
    return result


def compare(a: dict, b: dict) -> dict:
    """b minus a for every numeric measure both have."""
    keys = ["duration_s", "peak_db", "rms_db", "crest_db", "integrated_lufs",
            "spectral_centroid_hz", "spectral_rolloff_hz"]
    return {k: round(b[k] - a[k], 3) for k in keys if a.get(k) is not None and b.get(k) is not None}
