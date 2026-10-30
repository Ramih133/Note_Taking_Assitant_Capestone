"""Splits the lecture into topics and finds what the notes are missing."""

import os
import re
from collections import Counter
from difflib import SequenceMatcher

import string
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_VERBOSITY"] = "error"

import numpy as np
from sentence_transformers import SentenceTransformer

WINDOW = 3            # sentences per scored chunk
MIN_WORDS = 8
TILE = 4              # sentences compared on each side of a possible topic change
MIN_SEG = 6
DEPTH_STD = 0.5       # raise for fewer, bigger segments
NOTE_MIN = 0.30
THRESHOLD = 0.45
IMPORTANCE_PCT = 25   # least central 25% of chunks count as filler (jokes, credits)
NAME_PCT = 30         # names only count if said in a sentence above this centrality

model = SentenceTransformer("all-MiniLM-L6-v2")
cache = {}  # live re-checks run every 15s, so only new text gets embedded

STOP = ENGLISH_STOP_WORDS | set("""
uh um oh ok okay yeah gonna wanna actually basically really right just like kind sort
know think mean means say says want way thing things let lets let's make makes
did does doing having got gets getting goes going use used using second
it's that's thats there's here's what's i'm we're you're don't can't
value values number calculate called equal equals example
squared cubed minus plus times divided raised power half zero
""".split())

CAP_IGNORE = STOP | set("""
i'll i've i'd mr mrs ms dr hey yes thanks thank today tomorrow god bce ce ad bc pm
monday tuesday wednesday thursday friday saturday sunday
""".split())

PUNCT = string.punctuation


def embed(texts: list[str]) -> np.ndarray:
    """Turns each piece of text into numbers the model can compare. Saves results so it doesn't redo old text."""
    new = [t for t in set(texts) if t not in cache]
    if new:
        cache.update(zip(new, model.encode(new, normalize_embeddings=True)))
    return np.array([cache[t] for t in texts])


def split_sentences(lines: list[dict]) -> list[tuple[str, str]]:
    """Breaks the transcript into sentences and keeps the time each one was said."""
    out = []
    for line in lines:
        for s in re.split(r"(?<=[.!?])\s+", line["text"]):
            if s.strip():
                out.append((line["stamp"], s.strip()))
    return out


def note_lines(notes_text: str) -> list[str]:
    """Turns the notes into a list, one note per line, without bullet points or empty lines."""
    lines = [l.strip(" -*•#\t") for l in notes_text.splitlines()]
    return [l for l in lines if l]


def is_number(word: str) -> bool:
    """Checks if a word is a number like 81 or 2.01."""
    return word.replace(".", "", 1).isdigit()


def find_names(sentence: str, common: set[str]) -> list[list[str]]:
    """Finds names and numbers in a sentence, like "Polybius" or "81".
    Skips normal words that just happen to be capitalized."""
    found, phrase = [], []
    words = sentence.split()
    for i, raw in enumerate(words):
        word = raw.strip(PUNCT)
        low = word.lower().removesuffix("'s")
        capped = i > 0 and word[:1].isupper() and low not in CAP_IGNORE
        if capped and len(low) > 2:
            phrase.append(low)
        if (not capped or raw[-1] in PUNCT) and phrase:
            found.append(phrase)
            phrase = []
        if is_number(word) and len(word) >= 2:   # single digits are everywhere in math
            found.append([word])
    if phrase:
        found.append(phrase)
    # "Thought Bubble", "Wrong Horse": every word also used normally, so not a real name
    return [p for p in found if is_number(p[0]) or not all(w in common for w in p)]


def in_notes(word: str, note_words: set[str]) -> bool:
    """Checks if a word shows up in the notes. Close spellings count, but numbers have to match exactly."""
    if word in note_words:
        return True
    if is_number(word):
        return False  # 1.9 vs 1.99 must not fuzzy-match
    # Carthage/Carthaginians, Antony/Anthony
    return any((len(w) >= 5 and w[:5] == word[:5]) or
               (abs(len(w) - len(word)) <= 2 and SequenceMatcher(None, w, word).ratio() >= 0.85)
               for w in note_words)


def find_boundaries(emb: np.ndarray) -> list[int]:
    """Finds where the lecture switches topics. Returns the sentence number where each topic starts."""
    n = len(emb)
    if n < 2 * MIN_SEG:
        return [0]

    sims = []
    for i in range(1, n):
        left = emb[max(0, i - TILE):i].mean(axis=0)
        right = emb[i:i + TILE].mean(axis=0)
        sims.append(left @ right / (np.linalg.norm(left) * np.linalg.norm(right)))
    sims = np.array(sims)

    # depth = how far a dip goes below the peaks on either side
    depth = np.zeros_like(sims)
    for j in range(len(sims)):
        l = r = j
        while l > 0 and sims[l - 1] >= sims[l]:
            l -= 1
        while r < len(sims) - 1 and sims[r + 1] >= sims[r]:
            r += 1
        depth[j] = (sims[l] - sims[j]) + (sims[r] - sims[j])

    cutoff = depth.mean() + DEPTH_STD * depth.std()
    starts = [0]
    for j in np.argsort(-depth):
        if depth[j] <= cutoff:
            break
        b = j + 1
        if MIN_SEG <= b <= n - MIN_SEG and all(abs(b - s) >= MIN_SEG for s in starts):
            starts.append(b)
    return sorted(starts)


def title_for(sentences: list[str], vec: np.ndarray) -> str:
    """Makes a short title for a topic from the words that come up most in it."""
    counts = Counter()
    for s in sentences:
        words = re.findall(r"[a-z']+", s.lower())
        for w, nxt in zip(words, words[1:] + [""]):
            if w in STOP or len(w) <= 2:
                continue
            counts[w] += 1
            if nxt and nxt not in STOP and len(nxt) > 2:
                counts[f"{w} {nxt}"] += 1
    options = [p for p, c in counts.most_common(40) if c >= 2] or [p for p, _ in counts.most_common(10)]
    if not options:
        return "Untitled"

    picked = []
    for i in np.argsort(-(embed(options) @ vec)):
        p = options[i]
        if not any(p in q or q in p for q in picked):  # skip "tangent" if "tangent line" is in
            picked.append(p)
        if len(picked) == 3:
            break
    return " · ".join(picked)


def spans(a: int, b: int) -> list[tuple[int, int]]:
    """Splits a topic into small groups of 3 sentences that overlap a bit so nothing gets cut off."""
    out, i = [], a
    while True:
        out.append((i, min(i + WINDOW, b)))
        if i + WINDOW >= b:
            return out
        i += WINDOW - 1


def is_flagged(w: dict, threshold: float = THRESHOLD) -> bool:
    """Decides if a part of the lecture is missing from the notes. Has to match isGap in index.html."""
    return w["important"] and (w["score"] < threshold or bool(w["names"]))


def analyze(lines: list[dict], notes_text: str,
            use_names: bool = True, use_importance: bool = True) -> list[dict]:
    """Runs everything. Splits the lecture into topics and checks each part against the notes.
    The use_ options are only there so evaluate.py can turn the new checks off."""
    sents = split_sentences(lines)
    if not sents:
        return []
    stamps = [s for s, _ in sents]
    texts = [t for _, t in sents]
    emb = embed(texts)

    centroid = emb.mean(axis=0)
    centrality = emb @ (centroid / np.linalg.norm(centroid))
    name_cut = np.percentile(centrality, NAME_PCT)
    common = {w.strip(PUNCT) for t in texts for w in t.split() if w[:1].islower()}

    notes = note_lines(notes_text)
    note_words = {w.strip(".'-") for w in re.findall(r"[a-z0-9.'-]+", notes_text.lower())}

    bounds = find_boundaries(emb) + [len(sents)]
    segments, seg_vecs, windows = [], [], []
    for k, (a, b) in enumerate(zip(bounds, bounds[1:]), 1):
        vec = emb[a:b].mean(axis=0)
        vec /= np.linalg.norm(vec)
        seg = {
            "id": k,
            "start": stamps[a],
            "end": stamps[b] if b < len(sents) else stamps[b - 1],
            "title": title_for(texts[a:b], vec),
            "windows": [],
            "notes": [],
        }
        seg_spans = spans(a, b)
        for i, j in seg_spans:
            text = " ".join(texts[i:j])
            if len(text.split()) < MIN_WORDS and len(seg_spans) > 1:
                continue
            missing = set()
            if use_names:
                for s in range(i, j):
                    if centrality[s] >= name_cut:
                        missing |= {" ".join(p) for p in find_names(texts[s], common)
                                    if not any(in_notes(w, note_words) for w in p)}
            w = {"stamp": stamps[i], "end": stamps[j - 1], "text": text,
                 "names": sorted(missing), "centrality": float(centrality[i:j].mean())}
            seg["windows"].append(w)
            windows.append(w)
        segments.append(seg)
        seg_vecs.append(vec)

    if notes:
        note_emb = embed(notes)
        scores = (embed([w["text"] for w in windows]) @ note_emb.T).max(axis=1)
        for note, row in zip(notes, note_emb @ np.array(seg_vecs).T):
            if row.max() >= NOTE_MIN:
                segments[row.argmax()]["notes"].append(note)
    else:
        scores = np.zeros(len(windows))

    imp_cut = np.percentile([w["centrality"] for w in windows], IMPORTANCE_PCT)
    for w, score in zip(windows, scores):
        w["score"] = round(float(score), 3)
        w["important"] = bool(not use_importance or w["centrality"] >= imp_cut)
        w["centrality"] = round(w["centrality"], 3)
    return segments
