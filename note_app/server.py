"""Runs the app. Start it with python server.py, then open http://127.0.0.1:8000"""

import re
import threading
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from recorder import Recorder, load_whisper, stamp

import gaps

BASE = Path(__file__).parent
SESSIONS = BASE / "sessions"
CHUNK_SECONDS = 15

app = FastAPI()
lock = threading.Lock()
state = {"lines": [], "notes": "", "session": None}


def on_text(stamp: str, text: str) -> None:
    """Saves each new piece of transcript to memory and to the session's transcript.txt."""
    # runs on the recorder thread, hence the lock
    with lock:
        state["lines"].append({"stamp": stamp, "text": text})
        if state["session"]:
            with open(state["session"] / "transcript.txt", "a", encoding="utf-8") as f:
                f.write(f"[{stamp}] {text}\n")


print("Loading models... :D")
recorder = Recorder(load_whisper(), chunk_seconds=CHUNK_SECONDS, on_text=on_text)


class Notes(BaseModel):
    """What the page sends when it sends notes."""

    text: str


class Transcript(BaseModel):
    """What the page sends when it imports a transcript file."""

    name: str
    text: str


STAMP = re.compile(r"^\[?(?:(\d+):)?(\d+):(\d{2})\]?\s*(.*)$")
WORDS_PER_SEC = 2.5  # about 150 words a minute, only used to guess times for plain text


def parse_transcript(text: str) -> list[dict]:
    """Turns a .txt transcript into lines like the recorder makes.
    Lines starting with [mm:ss] or [hh:mm:ss] keep their time. Plain text gets guessed times."""
    lines = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = STAMP.match(raw)
        if m:
            h, mins, secs, words = m.groups()
            seconds = int(h or 0) * 3600 + int(mins) * 60 + int(secs)
            if words:
                lines.append({"stamp": stamp(seconds), "text": words})
        elif lines and lines[-1]["stamp"] is not None:
            lines[-1]["text"] += " " + raw  # a line that wrapped in a timestamped file
        else:
            lines.append({"stamp": None, "text": raw})

    if lines and all(l["stamp"] is None for l in lines):
        # no times at all: split into sentences and space them out by word count
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(l["text"] for l in lines))
        lines, elapsed = [], 0.0
        for s in sentences:
            if s.strip():
                lines.append({"stamp": stamp(elapsed), "text": s.strip()})
                elapsed += len(s.split()) / WORDS_PER_SEC
    return [l for l in lines if l["stamp"] is not None]


def save_notes() -> None:
    """Writes the current notes to the session's notes.txt."""
    if state["session"]:
        (state["session"] / "notes.txt").write_text(state["notes"], encoding="utf-8")


@app.get("/")
def index():
    """Sends the page to the browser."""
    return FileResponse(BASE / "index.html")


@app.post("/start")
def start():
    """Makes a new session folder and starts recording."""
    if not recorder.running:
        session = SESSIONS / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session.mkdir(parents=True, exist_ok=True)
        with lock:
            state["lines"] = []
            state["session"] = session
        save_notes()
        recorder.start()
    return {"recording": True, "session": state["session"].name}


@app.post("/stop")
def stop():
    """Stops recording and saves the notes."""
    recorder.stop()
    with lock:
        save_notes()
    return {"recording": False}


@app.post("/import")
def import_transcript(transcript: Transcript):
    """Loads a .txt transcript into a new session, like it was just recorded."""
    if recorder.running:
        raise HTTPException(409, "Stop recording before importing a transcript.")
    lines = parse_transcript(transcript.text)
    if not lines:
        raise HTTPException(400, "No transcript text found in that file.")
    session = SESSIONS / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_imported")
    session.mkdir(parents=True, exist_ok=True)
    with lock:
        state["lines"] = lines
        state["session"] = session
        (session / "transcript.txt").write_text(
            "".join(f"[{l['stamp']}] {l['text']}\n" for l in lines), encoding="utf-8")
        (session / "source.txt").write_text(transcript.name, encoding="utf-8")
        save_notes()
    return {"session": session.name, "total": len(lines)}


@app.get("/status")
def status(since: int = 0):
    """Sends any transcript lines the page doesn't have yet. since = how many it already has."""
    with lock:
        return {
            "recording": recorder.running,
            "session": state["session"].name if state["session"] else None,
            "total": len(state["lines"]),
            "lines": state["lines"][since:],
            "notes": state["notes"] if since == 0 else None,
        }


@app.post("/notes")
def update_notes(notes: Notes):
    """Saves the notes whenever the student stops typing."""
    with lock:
        state["notes"] = notes.text
        save_notes()
    return {"ok": True}


@app.post("/gaps")
def check_gaps(notes: Notes):
    """Compares the notes to the transcript so far and sends back the topics and gaps."""
    with lock:
        state["notes"] = notes.text
        lines = list(state["lines"])
        save_notes()
    return {"segments": gaps.analyze(lines, notes.text)}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)