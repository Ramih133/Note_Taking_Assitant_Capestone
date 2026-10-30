"""Tests the gap finder on a folder with transcript.txt, notes.txt and answer_key.json.

python experiments/evaluate.py data/rome_test [--threshold 0.5] [--show]
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "note_app"))
import gaps  # noqa: E402


def secs(stamp: str) -> int:
    """Turns a time like 01:30 into seconds."""
    m, s = stamp.split(":")
    return int(m) * 60 + int(s)


def load_lines(path: Path) -> list[dict]:
    """Reads a transcript.txt into the same format the app uses."""
    lines = []
    for raw in open(path, encoding="utf-8"):
        m = re.match(r"\[(\d+:\d+)\]\s*(.*)", raw.strip())
        if m and m.group(2):
            lines.append({"stamp": m.group(1), "text": m.group(2)})
    return lines


def overlaps(w: dict, item: dict) -> bool:
    """Checks if a flagged part of the lecture lands inside an answer key time range."""
    return secs(w["stamp"]) <= secs(item["end"]) and secs(w["end"]) >= secs(item["start"])


def reason(w: dict) -> str:
    """Says why something got flagged."""
    if w["names"]:
        return "not in notes: " + ", ".join(w["names"])
    return f"match {w['score']:.2f}"


ap = argparse.ArgumentParser()
ap.add_argument("folder")
ap.add_argument("--threshold", type=float, default=gaps.THRESHOLD)
ap.add_argument("--show", action="store_true", help="print every flag")
args = ap.parse_args()

folder = Path(args.folder)
lines = load_lines(folder / "transcript.txt")
notes = (folder / "notes.txt").read_text(encoding="utf-8")
key_file = folder / "answer_key.json"
key = json.loads(key_file.read_text(encoding="utf-8")) if key_file.exists() else None

print(f"\n{folder.name} (threshold {args.threshold})")
for name, opts in [("baseline", dict(use_names=False, use_importance=False)),
                   ("improved", dict(use_names=True, use_importance=True))]:
    windows = [w for s in gaps.analyze(lines, notes, **opts) for w in s["windows"]]
    flagged = [w for w in windows if gaps.is_flagged(w, args.threshold)]
    print(f"\n== {name}: {len(flagged)} of {len(windows)} chunks flagged")

    if key:
        missing, filler = key["missing"], key.get("filler", [])
        hits = [m for m in missing if any(overlaps(w, m) for w in flagged)]
        on_filler = [w for w in flagged if any(overlaps(w, f) for f in filler)]
        wrong = [w for w in flagged if not any(overlaps(w, x) for x in missing + filler)]

        print(f"   caught:         {len(hits)} / {len(missing)}")
        for m in missing:
            print(f"     {'OK  ' if m in hits else 'MISS'} {m['start']}-{m['end']}  {m['what']}")
        print(f"   on filler:      {len(on_filler)}")
        print(f"   false alarms:   {len(wrong)}")
        for w in wrong:
            print(f"     [{w['stamp']}] {reason(w)}  {w['text'][:60]}")

    if args.show or not key:
        print("   all flags:")
        for w in flagged:
            print(f"     [{w['stamp']}-{w['end']}] {reason(w)}  {w['text'][:60]}")
