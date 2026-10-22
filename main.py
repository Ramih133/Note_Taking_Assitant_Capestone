import argparse
import json

from common import fmt_time
from notes import ORDER, find_missing, load_notes, note_quality, recap_missing
from slides import analyze_slides

# Print functions, does no analysis
def print_points(points, limit=None):
    ranked = sorted(points, key=lambda p: (ORDER[p["importance"]], -p["score"]))
    for p in ranked[:limit]:
        print(f"[{p['importance']:6}] slide {p['slide']:>2} | {str(p.get('section') or p['title'])[:22]:22} "
              f"| {p['type']:8} | {p['text'][:60]}")
        print(f"          {', '.join(p['reasons']) or '-'}")

def print_missing(missing):
    if not missing:
        print("Notes cover all High-importance points")
        return
    print(f"{len(missing)} High-importance point(s) missing:\n")
    for m in missing:
        print(f"- slide {m['slide']} | {m.get('section') or m['title']} | {m['text']}")
        print(f"    why important: {', '.join(m['reasons'])}")
        print(f"    closest note ({m['similarity']}): {m['best_match']}")

def print_quality(q):
    if "coverage" not in q:
        print(q["summary"])
        return
    print(f"Notes score: {q['score']}/100  ({q['coverage']} covered, weighted by importance)\n")
    for name in ("by_importance", "by_type", "by_section"):
        print(name.replace("_", " ").capitalize() + ":")
        for k, v in q[name].items():
            print(f"  {str(k):28} {v}")
        print()
    for key, heading in (("unlinked_lines", "Not linked to any slide (maybe from the audio, or off-topic):"),
                         ("verbatim_lines", "Copied word-for-word from slides:")):
        if q[key]:
            print(heading)
            for l in q[key]:
                print("  -", l)
            print()
    print("Tips:" if q["tips"] else "No issues found.")
    for t in q["tips"]:
        print("  -", t)


def print_recap(recaps):
    if not recaps:
        print("No sections need a recap")
        return
    for r in recaps:
        print(f"## {r['section']}  ({'slides' if '–' in r['slides'] else 'slide'} {r['slides']}, {r['coverage']} covered)")
        if r["summary"]:
            print(f"\n{r['summary']}\n")
        print("You missed:")
        for p in r["missing"]:
            print(f"  [{p['importance']}] {p['text']}  (slide {p['slide']})")
        if r["excerpts"]:
            print("What the prof said:")
            for t, s in r["excerpts"]:
                print(f"  [{fmt_time(t)}] {s}")
        print()


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main():
    # Defining Flags
    # The less obvious ones are llm and demo
    # llm = adds a short ai written recap of each section the student missed
    # demo - runs the pipeline on the built-in fake lecture data
    ap = argparse.ArgumentParser()
    ap.add_argument("--slides")
    ap.add_argument("--notes")
    ap.add_argument("--audio")
    ap.add_argument("--transcript", help="existing transcript.json instead of --audio")
    ap.add_argument("--llm", action="store_true", help="write recaps with a local LLM")
    ap.add_argument("--demo", action="store_true", help="run on built-in sample data")
    args = ap.parse_args()

    if args.demo:
        from sample_data import NOTES, TRANSCRIPT, make_test_deck
        slides_path, notes_text, transcript = make_test_deck(), NOTES, TRANSCRIPT
    else:
        if not (args.slides and args.notes):
            ap.error("--slides and --notes are required (or use --demo)")
        slides_path, notes_text = args.slides, load_notes(args.notes)
        transcript = None
        if args.transcript:
            with open(args.transcript, encoding="utf-8") as f:
                transcript = json.load(f)
        elif args.audio:
            from transcribe import transcribe
            transcript = transcribe(args.audio, out_path="transcript.json")

    # Analysis The Data
    section("Slide points")
    points = analyze_slides(slides_path, transcript)
    print_points(points)

    section("Missing High-importance points")
    print_missing(find_missing(points, notes_text))

    section("Notes quality")
    print_quality(note_quality(points, notes_text))

    section("Recap of missed sections")
    print_recap(recap_missing(points, notes_text, transcript, use_llm=args.llm))


if __name__ == "__main__":
    main()
