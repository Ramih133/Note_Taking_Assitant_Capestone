import re
import pymupdf

from collections import defaultdict
from Note_Taking_Assitant_Capestone.partner_app.common import BULLETS, clean, cos_sim, encode, similar


def load_notes(path):
    low = path.lower()
    if low.endswith(".pdf"):
        return "\n".join(page.get_text() for page in pymupdf.open(path))
    if low.endswith(".docx"):
        # Holy shows up if the file is docx
        import docx
        return "\n".join(p.text for p in docx.Document(path).paragraphs)
    with open(path, encoding="utf-8") as f:
        return f.read()


def note_sentences(text):
    sents = []
    for line in text.splitlines():
        line = clean(line)
        sents += [s.strip() for s in re.split(r"(?<=[.!?;])\s+", line) if len(s.strip()) >= 3]
    return sents


def split_notes(text):
    sents = note_sentences(text)
    return sents + [sents[i] + " " + sents[i + 1] for i in range(len(sents) - 1)]

# The cutoff that decides whether a slide point counts as covered by the notes.
DEFAULT_THRESHOLD = 0.55


def best_matches(points, notes_text):
    chunks = split_notes(notes_text)
    if not points or not chunks:
        return [(0.0, None)] * len(points)
    sims = cos_sim(encode([p["text"] for p in points]), encode(chunks))
    best = sims.max(dim=1)
    return [(float(v), chunks[int(i)]) for v, i in zip(best.values, best.indices)]


def coverage_flags(points, notes_text, threshold=DEFAULT_THRESHOLD):
    return [s >= threshold for s, _ in best_matches(points, notes_text)]


def find_missing(points, notes_text, levels=("High",), threshold=DEFAULT_THRESHOLD):
    targets = [p for p in points if p.get("importance") in levels]
    missing = [{**p, "best_match": m, "similarity": round(s, 2)}
               for p, (s, m) in zip(targets, best_matches(targets, notes_text)) if s < threshold]
    return sorted(missing, key=lambda p: -p["score"])


WEIGHTS = {"High": 3, "Medium": 2, "Low": 1}

UNLINKED_BELOW = 0.35                   # Checks if the content at all matches the lecture slides
VERBATIM_ABOVE = 0.9                    # Checks to see if the content is matched verbatim (word for word)


def _breakdown(points, covered, key):
    d = defaultdict(lambda: [0, 0])
    for p, c in zip(points, covered):
        k = p.get(key) or p.get("title") or f"slide {p['slide']}"
        d[k][0] += c
        d[k][1] += 1
    return {k: f"{a}/{b}" for k, (a, b) in d.items()}


def note_quality(points, notes_text, threshold=DEFAULT_THRESHOLD, skip_slides=(1,)):
    points = [p for p in points if p["slide"] not in skip_slides]
    lines = note_sentences(notes_text)
    if not points or not lines:
        return {"score": 0, "summary": "No notes or no lecture points to compare."}

    covered = coverage_flags(points, notes_text, threshold)

    total_w = sum(WEIGHTS[p["importance"]] for p in points)
    got_w = sum(WEIGHTS[p["importance"]] for p, c in zip(points, covered) if c)

    best_for_line = cos_sim(encode(lines), encode([p["text"] for p in points])).max(dim=1).values.tolist()
    unlinked = [l for l, s in zip(lines, best_for_line) if s < UNLINKED_BELOW]

    verbatim = [l for l in lines if len(l.split()) >= 4
                and max(similar(l, p["text"]) for p in points) >= VERBATIM_ABOVE]

    raw_lines = [l for l in notes_text.splitlines() if l.strip()]
    headings = [l.strip() for l in raw_lines
                if not l.strip().startswith(tuple(BULLETS.strip())) and len(l.split()) <= 5]

    tips = []
    high = [c for p, c in zip(points, covered) if p["importance"] == "High"]
    if high and not all(high):
        tips.append("You're missing High-importance points. Run find_missing() to see them.")
    for t in ("equation", "warning", "example"):
        of_type = [c for p, c in zip(points, covered) if p["type"] == t]
        if of_type and sum(of_type) / len(of_type) < 0.5:
            tips.append(f"Most {t}s from the lecture aren't in your notes.")
    if len(verbatim) > len(lines) * 0.3:
        tips.append("A lot of lines are copied straight from the slides. Try putting them in your own words.")
    if not headings:
        tips.append("No headings found. Splitting notes by topic makes them easier to review.")

    return {
        "score": round(got_w / total_w * 100),
        "coverage": f"{sum(covered)}/{len(points)} points",
        "by_importance": _breakdown(points, covered, "importance"),
        "by_type": _breakdown(points, covered, "type"),
        "by_section": _breakdown(points, covered, "section"),
        "unlinked_lines": unlinked,
        "verbatim_lines": verbatim,
        "headings": headings,
        "tips": tips,
    }

# With llm on, Qwen write a short recap for each section the student missed.
ORDER = {"High": 0, "Medium": 1, "Low": 2}
LLM_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
_llm = None


def transcript_excerpts(text, transcript, t_emb, k=2, min_sim=0.45):
    sims = cos_sim(encode(text), t_emb)[0]
    out = []
    for j in sims.argsort(descending=True)[:k].tolist():
        if float(sims[j]) < min_sim:
            break
        seg = transcript[j]["text"]
        if j + 1 < len(transcript):
            seg += " " + transcript[j + 1]["text"]
        out.append((transcript[j]["start"], seg))
    return out


def llm_recap(section, missing, excerpts):
    global _llm
    if _llm is None:
        from transformers import pipeline
        _llm = pipeline("text-generation", model=LLM_NAME, device_map="auto")
    facts = "\n".join(f"- {p['text']}" for p in missing)
    said = "\n".join(f"- {s}" for _, s in excerpts) or "(no transcript)"
    prompt = [
        {"role": "system", "content": "You help students fill gaps in their lecture notes. Use ONLY the "
         "information given. Do not add outside facts. Write 2-4 short sentences a student could add to their notes."},
        {"role": "user", "content": f"Section: {section}\n\nMissed slide points:\n{facts}\n\n"
         f"What the professor said:\n{said}\n\nRecap what was missed."},
    ]
    out = _llm(prompt, max_new_tokens=150, do_sample=False)
    return out[0]["generated_text"][-1]["content"].strip()


def recap_missing(points, notes_text, transcript=None, threshold=DEFAULT_THRESHOLD,
                  min_coverage=0.6, skip_slides=(1,), use_llm=False):
    points = [p for p in points if p["slide"] not in skip_slides]
    covered = coverage_flags(points, notes_text, threshold)

    sections = defaultdict(list)
    for p, c in zip(points, covered):
        sections[p.get("section") or p.get("title") or f"Slide {p['slide']}"].append((p, c))

    t_emb = encode([t["text"] for t in transcript]) if transcript else None

    recaps = []
    for name, items in sections.items():
        missing = sorted([p for p, c in items if not c], key=lambda p: ORDER[p["importance"]])
        cov = sum(c for _, c in items) / len(items)
        if not missing or (cov >= min_coverage and all(p["importance"] != "High" for p in missing)):
            continue
        excerpts = []
        if t_emb is not None:
            for p in missing:
                excerpts += transcript_excerpts(p["text"], transcript, t_emb)
            excerpts = sorted(dict(excerpts).items())
        slides = sorted({p["slide"] for p, _ in items})
        recaps.append({
            "section": name,
            "slides": f"{slides[0]}–{slides[-1]}" if len(slides) > 1 else str(slides[0]),
            "coverage": f"{sum(c for _, c in items)}/{len(items)}",
            "missing": missing,
            "excerpts": excerpts,
            "summary": llm_recap(name, missing, excerpts) if use_llm else None,
        })
    return sorted(recaps, key=lambda r: min(ORDER[p["importance"]] for p in r["missing"]))
