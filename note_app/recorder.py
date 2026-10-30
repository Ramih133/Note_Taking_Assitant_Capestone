"""Records the mic and turns speech into text with Whisper."""

import os
import queue
import sys
import threading
from collections.abc import Callable

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


def add_cuda_dlls() -> None:
    """Helps Windows find the GPU files that pip installed inside the venv. Does nothing on Mac/Linux."""
    if os.name != "nt":
        return
    base = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
    for sub in ("cublas", "cudnn"):
        path = os.path.join(base, sub, "bin")
        if os.path.isdir(path):
            os.add_dll_directory(path)
            os.environ["PATH"] = path + os.pathsep + os.environ["PATH"]


add_cuda_dlls()  # has to happen before faster_whisper is imported

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SR = 16000


def load_whisper() -> WhisperModel:
    """Loads Whisper on the GPU. If the GPU doesn't work, falls back to a smaller model on the CPU."""
    try:
        model = WhisperModel("small.en", device="cuda", compute_type="float16")
        # missing CUDA libs only error on the first transcribe, so test it now
        segs, _ = model.transcribe(np.zeros(SR, dtype=np.float32), vad_filter=False)
        list(segs)
        print("Whisper: using GPU.")
        return model
    except Exception as e:
        print(f"Whisper: GPU not usable ({e}). Using CPU.")
        return WhisperModel("base.en", device="cpu", compute_type="int8")


def stamp(seconds: float) -> str:
    """Turns seconds into a time like 01:30."""
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


class Recorder:
    """Records the mic and turns it into text, a chunk at a time, in the background."""

    def __init__(self, model: WhisperModel, chunk_seconds: int = 15,
                 on_text: Callable[[str, str], None] | None = None):
        """on_text gets called with (time, text) every time a chunk is done."""
        self.model = model
        self.chunk_len = chunk_seconds * SR
        self.on_text = on_text
        self.running = False
        self.stream = None
        self.thread = None
        self.q = queue.Queue()
        self.elapsed = 0.0

    def _mic_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Gets called by the mic every few milliseconds. Just saves the audio for later."""
        self.q.put(indata[:, 0].copy())

    def start(self, device: int | None = None) -> None:
        """Starts recording. device is the mic number, leave it empty to use the default mic."""
        if self.running:
            return
        self.running = True
        self.elapsed = 0.0
        self.q = queue.Queue()
        self.stream = sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                                     callback=self._mic_callback, device=device)
        self.stream.start()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        """Stops recording and waits for the last chunk to finish."""
        if not self.running:
            return
        self.running = False
        self.stream.stop()
        self.stream.close()
        self.thread.join()

    def _loop(self) -> None:
        """Collects audio until there's a full chunk, then turns it into text. Runs in the background."""
        # the mic keeps filling the queue while a chunk is transcribing, so nothing is lost
        buffer = np.zeros(0, dtype=np.float32)
        while self.running or not self.q.empty():
            try:
                buffer = np.concatenate([buffer, self.q.get(timeout=0.5)])
            except queue.Empty:
                continue
            if len(buffer) >= self.chunk_len:
                chunk, buffer = buffer[:self.chunk_len], buffer[self.chunk_len:]
                self._handle(chunk)
        if len(buffer) > SR:
            self._handle(buffer)

    def _handle(self, chunk: np.ndarray) -> None:
        """Turns one chunk of audio into text and sends it to on_text."""
        segments, _ = self.model.transcribe(chunk, language="en", vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
        if text and self.on_text:
            self.on_text(stamp(self.elapsed), text)
        self.elapsed += len(chunk) / SR
