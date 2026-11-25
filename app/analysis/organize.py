"""Organize a student's notes into topic sections and subsections that follow the lecture.

Lecture structure comes from whatever the note has:
  transcript + slides -> sections = lecture topics (topic detection from gaps.py), subsections = slide titles
  transcript only     -> sections = lecture topics, subsections = smaller topics inside each one
  slides only         -> sections = slide titles
  nothing             -> the notes' own topics (same topic detection, run on the notes)
Each note line goes under the closest topic using the fine-tuned matcher. Lines that fit no
lecture topic but are still on the subject (relevance score) are grouped into new topics marked
"from your notes". Only off-subject lines go under "Other notes". The student's wording is never
changed, only moved.
"""

import re

import numpy as np

FIT_MIN = 0.25      # below this a note line doesn't belong to any lecture topic
RELATED_MIN = 0.15  # floor for "still on the lecture's subject" (see new_topics_from_leftovers)
RELATIVE = 0.5      # ...or half the typical score of lines that did fit a topic, if that's higher
GROUP_MIN = 0.45    # how similar on-subject leftover lines must be to share a new topic


def note_lines(text: str) -> list[str]:
    lines = [re.sub(r"^[\s\-*•·>#\d.)]+", "", l).strip() for l in (text or "").splitlines()]
    return [l for l in lines if len(l) > 1]


def slide_targets(slides: list[dict]) -> list[dict]:
    """[{slide, text}] (one per PDF page) -> topics titled by each slide's first line.
    Consecutive slides with the same title merge."""
    out = []
    for s in slides:
        lines = [l.strip() for l in (s.get("text") or "").splitlines() if l.strip()]
        if not lines:
            continue
        title = lines[0][:80]
        if out and out[-1]["title"].lower() == title.lower():
            out[-1]["text"] += " " + " ".join(lines[1:])
        else:
            out.append({"title": title, "text": " ".join(lines), "order": len(out)})
    return out


def topic_spans(emb: np.ndarray, boundaries) -> list[tuple[int, int]]:
    starts = boundaries(emb)
    return [(a, b) for a, b in zip(starts, starts[1:] + [len(emb)])]


def merge_adjacent(spans, emb, target):
    """Merge the most similar neighbouring topics until there are `target` of them.
    Returns groups of the original spans, so small topics can become subsections."""
    groups = [[sp] for sp in spans]
    def vec(g):
        v = emb[g[0][0]:g[-1][1]].mean(axis=0)
        return v / (np.linalg.norm(v) or 1)
    total = spans[-1][1] - spans[0][0] if spans else 1
    size = lambda g: (g[-1][1] - g[0][0]) / total
    while len(groups) > target:
        # similar neighbours merge first, but big merges are penalised so sections stay balanced
        sims = [vec(groups[i]) @ vec(groups[i + 1]) - size(groups[i] + groups[i + 1])
                for i in range(len(groups) - 1)]
        i = int(np.argmax(sims))
        groups[i:i + 2] = [groups[i] + groups[i + 1]]
    return groups


def transcript_targets(sentences: list[str], embed, boundaries, title_for, sub_topics: bool) -> list[dict]:
    """Lecture topics from the transcript, merged into about one section per ~35 sentences
    (2-8 sections). With sub_topics=True the small topics stay as each section's subsections."""
    emb = embed(sentences)
    spans = topic_spans(emb, boundaries)
    target = min(8, max(2, round(len(sentences) / 35)))
    groups = merge_adjacent(spans, emb, target)
    out = []
    for g in groups:
        a, b = g[0][0], g[-1][1]
        sec = {"title": title_for(sentences[a:b], emb[a:b].mean(axis=0)), "text": " ".join(sentences[a:b]),
               "order": len(out), "subs": []}
        if sub_topics and len(g) > 1:
            for c, d in g:
                sec["subs"].append({"title": title_for(sentences[c:d], emb[c:d].mean(axis=0)),
                                    "text": " ".join(sentences[c:d]), "order": len(sec["subs"])})
        out.append(sec)
    return out


def attach_slides(sections: list[dict], slides: list[dict], embed):
    """Each slide becomes a subsection of the lecture topic it's closest to."""
    if not sections or not slides:
        return
    sim = embed([s["text"] for s in slides]) @ embed([s["text"] for s in sections]).T
    for i, s in enumerate(slides):
        sections[int(sim[i].argmax())]["subs"].append({**s, "order": s["order"]})


def organize(notes_text: str, embed, boundaries, title_for,
             transcript: list[str] | None = None, slides: list[dict] | None = None) -> list[dict]:
    """-> [{title, lines, subs: [{title, lines}]}], in lecture order."""
    lines = note_lines(notes_text)
    if not lines:
        return []
    slides = slide_targets(slides or [])
    transcript = [s for s in (transcript or []) if s.strip()]

    if transcript:
        sections = transcript_targets(transcript, embed, boundaries, title_for, sub_topics=not slides)
        attach_slides(sections, slides, embed)
    elif slides:
        sections = [{**s, "subs": []} for s in slides]
    else:  # no lecture material: find the topics in the notes themselves
        sections = transcript_targets(lines, embed, boundaries, title_for, sub_topics=True)

    # leaves = every subsection, plus sections that have none
    leaves = []
    for si, sec in enumerate(sections):
        sec["lines"] = []
        for sub in sec["subs"]:
            sub["lines"] = []
            leaves.append((si, sub))
        if not sec["subs"]:
            leaves.append((si, None))
    texts = [(sub or sections[si])["text"] for si, sub in leaves]
    sim = embed(lines) @ embed(texts).T

    leftover, placed_scores = [], []
    for i, line in enumerate(lines):
        j = int(sim[i].argmax())
        if sim[i, j] < FIT_MIN:
            leftover.append(i)
            continue
        placed_scores.append(float(sim[i, j]))
        si, sub = leaves[j]
        (sub if sub is not None else sections[si])["lines"].append(line)

    result = []
    for sec in sections:
        subs = [{"title": s["title"], "lines": s["lines"]} for s in sec["subs"] if s["lines"]]
        if sec["lines"] or subs:
            result.append({"title": sec["title"], "lines": sec["lines"], "subs": subs, "new": False})
    new_topics, other = new_topics_from_leftovers(lines, leftover, sim, embed, title_for, texts, placed_scores)
    if not (transcript or slides):  # every topic came from the notes, so don't mark these as extra
        for t in new_topics:
            t["new"] = False
    result += new_topics
    if other:
        result.append({"title": "Other notes", "lines": other, "subs": [], "new": False})
    return result


def relevance(sim_row: np.ndarray, line_vec: np.ndarray, subject: np.ndarray) -> float:
    """How on-subject a note line is: its best match to any lecture topic, or to the lecture as a whole."""
    return max(float(sim_row.max()), float(line_vec @ subject))


def new_topics_from_leftovers(lines, leftover, sim, embed, title_for, topic_texts, placed_scores):
    """Lines that fit no lecture topic. On-subject ones (relevance score) become new topics:
    groups of similar lines get a topic each, and the rest share one "More on this lecture" topic.
    Off-subject lines are returned as "other"."""
    if not leftover:
        return [], []
    vecs = embed([lines[i] for i in leftover])
    subject = embed(topic_texts).mean(axis=0)
    subject = subject / (np.linalg.norm(subject) or 1)
    cut = max(RELATED_MIN, RELATIVE * float(np.median(placed_scores))) if placed_scores else RELATED_MIN

    related, other = [], []
    for k, i in enumerate(leftover):
        (related if relevance(sim[i], vecs[k], subject) >= cut else other).append((k, i))

    # greedy grouping in note order: join the most similar group, or start a new one
    groups = []
    for k, i in related:
        best, best_sim = None, GROUP_MIN
        for g in groups:
            c = vecs[g["ks"]].mean(axis=0)
            c_sim = float(vecs[k] @ (c / (np.linalg.norm(c) or 1)))
            if c_sim >= best_sim:
                best, best_sim = g, c_sim
        if best is None:
            groups.append({"ks": [k], "lines": [i]})
        else:
            best["ks"].append(k)
            best["lines"].append(i)

    topics, loose = [], []
    for g in groups:
        if len(g["lines"]) >= 2:
            group_lines = [lines[i] for i in g["lines"]]
            topics.append({"title": title_for(group_lines, vecs[g["ks"]].mean(axis=0)),
                           "lines": group_lines, "subs": [], "new": True})
        else:
            loose += g["lines"]
    if loose:
        topics.append({"title": "More on this lecture", "lines": [lines[i] for i in sorted(loose)],
                       "subs": [], "new": True})
    return topics, [lines[i] for _, i in other]


def to_html(sections: list[dict]) -> str:
    import html
    esc = html.escape
    parts = []
    for sec in sections:
        mark = " (from your notes, not in the lecture)" if sec.get("new") else ""
        parts.append(f"<h2>{esc(sec['title'])}{mark}</h2>")
        if sec["lines"]:
            parts.append("<ul>" + "".join(f"<li>{esc(l)}</li>" for l in sec["lines"]) + "</ul>")
        for sub in sec["subs"]:
            parts.append(f"<h3>{esc(sub['title'])}</h3>")
            parts.append("<ul>" + "".join(f"<li>{esc(l)}</li>" for l in sub["lines"]) + "</ul>")
    return "".join(parts)


TITLE_PROMPT = """Give a short title (2-5 words) for this part of a lecture. Answer with the title only.

{text}"""


def llm_titler(generate, fallback):
    """Section titles from the local LLM, falling back to keyword titles."""
    def title_for(sentences, vec):
        text = " ".join(sentences)
        words = text.split()
        if generate is None or len(words) < 15:
            return fallback(sentences, vec)
        try:
            reply = generate([{"role": "user", "content": TITLE_PROMPT.format(text=" ".join(words[:400]))}], 16)
            title = re.sub(r"[\"'*#]|^title:\s*", "", (reply or "").strip().splitlines()[0], flags=re.I).strip(" .:")
            if 2 <= len(title) <= 60:
                return title
        except Exception:
            pass
        return fallback(sentences, vec)
    return title_for


def run(notes_text: str, transcript_lines=None, slides=None, generate="auto") -> list[dict]:
    """App entry point: uses the matcher and topic detection from gaps.py, and Qwen for titles if it's available."""
    from analysis import gaps
    if generate == "auto":
        try:
            from analysis.quiz_llm import llm_available, get_generator
            generate = get_generator() if llm_available() else None
        except Exception:
            generate = None
    sentences = [t for _, t in gaps.split_sentences(transcript_lines or [])] if transcript_lines else []
    titler = llm_titler(generate, gaps.title_for)
    return organize(notes_text, gaps.embed, gaps.find_boundaries, titler, sentences, slides)
