"""Runs the app. Start it with python server.py, then open http://127.0.0.1:8000"""

import threading
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from recorder import Recorder, load_whisper
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


print("Loading models...")
recorder = Recorder(load_whisper(), chunk_seconds=CHUNK_SECONDS, on_text=on_text)


class Notes(BaseModel):
    """What the page sends when it sends notes."""

    text: str


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
