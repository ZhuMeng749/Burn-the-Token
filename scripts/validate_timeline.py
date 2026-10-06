#!/usr/bin/env python3
"""Validate timeline structure; no media decoding, perceptual review or rendering.

Usage: python3 validate_timeline.py /path/to/timeline.json
Exit: 0 valid structure, 1 validation errors, 2 unreadable/invalid JSON.
Paths are resolved relative to timeline.json. Uses only Python standard library.
"""

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import sys


def validate(data, base):
    errors = []

    def problem(message):
        errors.append(message)

    def integer(value):
        return isinstance(value, int) and not isinstance(value, bool)

    def number(value):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value))

    if not isinstance(data, dict):
        return ["Timeline must be a JSON object"]
    if data.get("schema_version") != 1:
        problem("schema_version must be 1")
    if data.get("precision") != "locked":
        problem("precision must be locked; estimated timings are not final")
    comp = data.get("composition")
    if not isinstance(comp, dict):
        return errors + ["composition must be an object"]
    for key in ("width", "height", "duration_frames"):
        if not integer(comp.get(key)) or comp[key] <= 0:
            problem("composition.%s must be a positive integer" % key)
    try:
        fps = Fraction(str(comp.get("fps")))
        if fps <= 0:
            raise ValueError()
    except (ValueError, ZeroDivisionError):
        return errors + ["composition.fps must be a positive number or fraction"]
    total = comp.get("duration_frames")
    if not integer(total) or total <= 0:
        return errors

    def interval(item, label):
        start, end = item.get("start_frame"), item.get("end_frame")
        if (not integer(start) or not integer(end)
                or not 0 <= start < end <= total):
            problem("%s must have integer interval 0 <= start < end <= duration" % label)
            return None
        return start, end

    review = data.get("review_range")
    if not isinstance(review, dict):
        return errors + ["review_range must be an object"]
    bounds = interval(review, "review_range")
    if bounds is None:
        return errors

    def rows(key):
        items = data.get(key)
        if not isinstance(items, list):
            problem("%s must be a list" % key)
            return []
        valid = []
        ids = set()
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                problem("%s[%s] must be an object" % (key, i))
                continue
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id.strip():
                problem("%s[%s] needs a non-empty id" % (key, i))
            elif item_id in ids:
                problem("Duplicate id in %s: %s" % (key, item_id))
            else:
                ids.add(item_id)
            valid.append(item)
        return valid

    assets = {}
    for item in rows("assets"):
        key = item.get("id")
        if isinstance(key, str):
            assets[key] = item

    def asset_for(asset_id, label):
        if not isinstance(asset_id, str) or asset_id not in assets:
            problem("%s uses unknown asset %r" % (label, asset_id))
            return None
        asset = assets[asset_id]
        if asset.get("role") == "reference":
            problem("%s uses reference-only media in the production" % label)
        path = asset.get("path")
        if not isinstance(path, str) or not path:
            problem("%s asset needs a local path" % label)
        elif not (base / Path(path).expanduser()).is_file():
            problem("%s asset file missing: %s" % (label, path))
        return asset

    def clipped(segment):
        start, end = max(segment[0], bounds[0]), min(segment[1], bounds[1])
        return (start, end) if start < end else None

    def coverage(segments, label):
        cursor = bounds[0]
        for start, end in sorted(segments):
            if start > cursor:
                problem("%s gap at frames [%s, %s)" % (label, cursor, start))
            cursor = max(cursor, end)
        if cursor < bounds[1]:
            problem("%s gap at frames [%s, %s)" % (label, cursor, bounds[1]))

    shots = []
    for shot in rows("shots"):
        label = "shot %s" % shot.get("id")
        span = interval(shot, label)
        if span:
            shots.append((span, shot))
        refs = shot.get("asset_ids")
        if not isinstance(refs, list):
            problem("%s asset_ids must be a list (empty for code-only scenes)" % label)
        else:
            for ref in refs:
                asset_for(ref, label)
        if not isinstance(shot.get("script_ids"), list) or not shot["script_ids"]:
            problem("%s needs script_ids" % label)
    coverage([c for span, _ in shots if (c := clipped(span))], "Picture")
    shots.sort(key=lambda x: x[0])
    for i, (span, shot) in enumerate(shots):
        for previous_span, previous in shots[:i]:
            if (span[0] < previous_span[1]
                    and not (shot.get("transition_overlap") is True
                             or previous.get("transition_overlap") is True)):
                problem("Unmarked picture overlap: %s / %s" % (previous.get("id"), shot.get("id")))

    speech = []
    for clip in rows("audio_clips"):
        label = "audio %s" % clip.get("id")
        span = interval(clip, label)
        kind = clip.get("kind")
        if not isinstance(kind, str) or kind not in {"speech", "music", "sfx", "ambience"}:
            problem("%s has invalid kind" % label)
        if kind == "speech":
            route = clip.get("route")
            if not isinstance(route, str) or route not in {"presenter_original", "clone", "master"}:
                problem("%s needs a valid speech route" % label)
            if span:
                speech.append((span, clip.get("id")))
        asset = asset_for(clip.get("asset_id"), label)
        speed = clip.get("speed", 1)
        source_in = clip.get("source_in_seconds")
        gain = clip.get("gain_db")
        if not number(gain):
            problem("%s needs finite gain_db for an enabled audio region" % label)
        if not number(speed) or speed <= 0:
            problem("%s speed must be positive" % label)
            continue
        if not number(source_in) or source_in < 0:
            problem("%s source_in_seconds must be non-negative" % label)
            continue
        duration = asset.get("duration_seconds") if asset else None
        if not number(duration) or duration <= 0:
            problem("%s needs probed asset duration_seconds" % label)
            continue
        if source_in >= duration:
            problem("%s source in-point is outside media" % label)
        loop = clip.get("loop", False)
        if not isinstance(loop, bool):
            problem("%s loop must be boolean" % label)
        if loop and kind == "speech":
            problem("%s cannot loop spoken words" % label)
        if span and not loop:
            needed = float(Fraction(span[1] - span[0], 1) / fps) * speed
            if source_in + needed > duration + 1e-6:
                problem("%s extends beyond source media" % label)

    speech.sort(key=lambda x: x[0])
    for i, (span, item_id) in enumerate(speech):
        for other, other_id in speech[:i]:
            if span[0] < other[1]:
                problem("Overlapping speech (possible double voice): %s / %s" % (other_id, item_id))

    silences = []
    for silence in rows("intentional_silences"):
        label = "silence %s" % silence.get("id")
        span = interval(silence, label)
        if not isinstance(silence.get("reason"), str) or not silence["reason"].strip():
            problem("%s needs a reason" % label)
        if span:
            silences.append(span)
            for voice_span, voice_id in speech:
                if max(span[0], voice_span[0]) < min(span[1], voice_span[1]):
                    problem("%s overlaps spoken clip %s" % (label, voice_id))
    coverage([c for span in [s for s, _ in speech] + silences if (c := clipped(span))], "Voice/silence")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.timeline.read_text(encoding="utf-8"))
        errors = validate(data, args.timeline.resolve().parent)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "ok": not errors,
        "scope": "structure_only; media playback, source truth and user approvals are not verified",
        "errors": errors,
    }, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
