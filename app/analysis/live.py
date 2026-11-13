"""Holds the live lecture session (one at a time) for the /live/ routes in app.py.

state["owner"] says whose session it is: a lecture id (int) for the lecture page,
or "note:<id>" for a Studio notebook note.
"""

import re
import threading

lock = threading.Lock()
state = {"owner": None, "lines": [], "recorder": None}


def _on_text(stamp, text):
    """Called by the recorder thread each time a 15s chunk is transcribed."""
    with lock:
        state["lines"].append({"stamp": stamp, "text": text})


def get_recorder():
    """Loads Whisper the first time someone hits Start, not when the app boots."""
    if state["recorder"] is None:
        from analysis.recorder import Recorder, load_whisper
        state["recorder"] = Recorder(load_whisper(), chunk_seconds=15, on_text=_on_text)
    return state["recorder"]


def is_recording(owner):
    rec = state["recorder"]
    return bool(rec and rec.running and state["owner"] == owner)


def _stamp(seconds):
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def to_segments(lines):
    """Live lines ({stamp: "mm:ss", text}) -> the transcript format load_transcript() reads."""
    def secs(s):
        m, sec = s.split(":")
        return int(m) * 60 + int(sec)
    out = [{"start": float(secs(l["stamp"])), "text": l["text"]} for l in lines]
    for a, b in zip(out, out[1:] + [None]):
        a["end"] = b["start"] if b else a["start"] + 15.0
    return out


STAMP = re.compile(r"^\[?(?:(\d+):)?(\d+):(\d{2})\]?\s*(.*)$")
WORDS_PER_SEC = 2.5  # ~150 words a minute, only used to guess times for plain text


def parse_transcript(text):
    """A .txt transcript -> live lines. Lines starting with [mm:ss] or [hh:mm:ss] keep their
    time; plain text gets split into sentences with guessed times. (From note_app/server.py.)"""
    lines = []
    for raw in (text or "").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = STAMP.match(raw)
        if m:
            h, mins, secs, words = m.groups()
            if words:
                lines.append({"stamp": _stamp(int(h or 0) * 3600 + int(mins) * 60 + int(secs)), "text": words})
        elif lines and lines[-1]["stamp"] is not None:
            lines[-1]["text"] += " " + raw  # a wrapped line in a timestamped file
        else:
            lines.append({"stamp": None, "text": raw})

    if lines and all(l["stamp"] is None for l in lines):
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(l["text"] for l in lines))
        lines, elapsed = [], 0.0
        for s in sentences:
            if s.strip():
                lines.append({"stamp": _stamp(elapsed), "text": s.strip()})
                elapsed += len(s.split()) / WORDS_PER_SEC
    return [l for l in lines if l["stamp"] is not None]