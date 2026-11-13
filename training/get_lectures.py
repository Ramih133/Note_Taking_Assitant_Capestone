#!/usr/bin/env python3
"""
Download lecture transcripts from a YouTube playlist into data/transcripts/ (one .txt per lecture).

Two modes:
  subs     (default) grab the existing English captions - fast, no GPU needed
  whisper  download the audio and transcribe with faster-whisper - slow, but the text
           looks exactly like what your app produces, so it's the better match for training

  python get_lectures.py "<playlist url>" --prefix ai6034
  python get_lectures.py "<playlist url>" --prefix algo6006 --max 10
  python get_lectures.py "<playlist url>" --prefix la1806 --mode whisper --whisper-model small

--prefix becomes the start of every file name (ai6034_001.txt, ...), so lectures from different
courses don't overwrite each other. Run it once per playlist.

pip install yt-dlp faster-whisper
"""
import argparse
import re
import shutil
from pathlib import Path


def vtt_to_text(vtt):
    """Strip timestamps/tags from a .vtt file and drop the repeated lines auto-captions produce."""
    lines, prev = [], None
    for line in vtt.splitlines():
        line = line.strip()
        if (not line or line == "WEBVTT" or "-->" in line or line.isdigit()
                or line.startswith(("Kind:", "Language:", "NOTE"))):
            continue
        line = re.sub(r"<[^>]+>", "", line)          # <c>, <00:00:01.000> etc.
        line = re.sub(r"\[(music|applause|laughter|inaudible)\]", "", line, flags=re.I).strip()
        if line and line != prev:
            lines.append(line)
            prev = line
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def download(url, tmp, a, audio):
    from yt_dlp import YoutubeDL
    opts = {
        "outtmpl": str(tmp / "%(playlist_index)03d.%(ext)s"),
        "ignoreerrors": True,      # one broken video shouldn't kill the whole playlist
        "quiet": True,
        "no_warnings": True,
    }
    if a.max:
        opts["playlistend"] = a.max
    if audio:
        opts["format"] = "bestaudio/best"
    else:
        opts.update({
            "skip_download": True,
            "writesubtitles": True,               # human-made captions
            "writeautomaticsub": a.auto,          # YouTube auto-captions as fallback
            "subtitleslangs": ["en", "en-US", "en-GB"],
            "subtitlesformat": "vtt",
        })
    with YoutubeDL(opts) as ydl:
        ydl.download([url])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url", help="YouTube playlist (or single video) URL")
    p.add_argument("--prefix", required=True, help="short course id used in file names, e.g. ai6034")
    p.add_argument("--out", default="data/transcripts")
    p.add_argument("--max", type=int, default=0, help="only the first N videos (0 = all)")
    p.add_argument("--mode", choices=["subs", "whisper"], default="subs")
    p.add_argument("--auto", action="store_true",
                   help="subs mode: allow YouTube auto-captions if no human captions exist "
                        "(lower quality, little punctuation)")
    p.add_argument("--whisper-model", default="small", help="tiny/base/small/medium/large-v3")
    a = p.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(".lecture_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()

    try:
        download(a.url, tmp, a, audio=(a.mode == "whisper"))
        files = sorted(tmp.iterdir())
        if not files:
            raise SystemExit("Nothing downloaded. Check the URL, or try --auto if the videos "
                             "only have auto-captions.")

        model = None
        if a.mode == "whisper":
            from faster_whisper import WhisperModel
            model = WhisperModel(a.whisper_model, device="auto", compute_type="default")

        for f in files:
            idx = f.name.split(".")[0]
            dest = out / f"{a.prefix}_{idx}.txt"
            if dest.exists():
                print(f"skip {dest.name} (exists)")
                continue
            if model:
                print(f"transcribing {f.name}...")
                segments, _ = model.transcribe(str(f), vad_filter=True)
                text = " ".join(s.text.strip() for s in segments)
            else:
                text = vtt_to_text(f.read_text(encoding="utf-8", errors="ignore"))
            if len(text.split()) < 300:
                print(f"skip {dest.name} (only {len(text.split())} words - probably not a lecture)")
                continue
            dest.write_text(text, encoding="utf-8")
            print(f"saved {dest.name} ({len(text.split())} words)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()