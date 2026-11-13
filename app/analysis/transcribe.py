import json
import os
import time

# transcribe.py is used to convert audio to text

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import librosa
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000

# Loads the model (whisper)
def load_whisper(size="small"):
    try:
        # runs the faster-whipster on GPU, otherwise runs CPU8
        import torch
        if torch.cuda.is_available():
            return WhisperModel(size, device="cuda", compute_type="float16")
    except ImportError:
        pass
    return WhisperModel(size, device="cpu", compute_type="int8")


def transcribe(audio_path, model_size="small", out_path=None):
    model = load_whisper(model_size)
    audio, _ = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)

    start = time.perf_counter()
    segments, _ = model.transcribe(audio)
    transcript = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
                  for s in segments]
    elapsed = time.perf_counter() - start

    print(f"{len(transcript)} segments | audio {len(audio) / SAMPLE_RATE / 60:.1f} min "
          f"| took {elapsed / 60:.1f} min")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(transcript, f, indent=2, ensure_ascii=False)
    return transcript
