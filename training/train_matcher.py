"""
How to use
1. run 'python train_matcher.py gen --transcripts data/transcripts --model llama3.1:8b'
2. run 'python train_matcher.py train --base all-MiniLM-L6-v2'
3. run 'python train_matcher.py eval --models all-MiniLM-L6-v2 models/notes-matcher'

python train_matcher.py gen --transcripts data/transcripts --model llama3.1:8b
python train_matcher.py train --base all-MiniLM-L6-v2
python train_matcher.py eval --models all-MiniLM-L6-v2 models/notes-matcher

"""

import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path

DEFAULT_BASE = "sentence-transformers/all-MiniLM-L6-v2"

STYLES = [
    "terse bullet points with heavy abbreviations (w/, b/c, ->, =, approx, def.), no full sentences",
    "only the single main idea, one short line, in your own words",
    "casual paraphrase, 1-2 lines, ideas maybe in a different order than the professor said them",
    "rushed keyword fragments and arrows, some details dropped",
    "one clean sentence summarizing it in your own words",
    "a question or reminder to yourself about the key point (e.g. 'why does X -> Y? check slides')",
]

PROMPT = """You are a university student taking notes during a lecture. The professor just said:
 
\"\"\"{chunk}\"\"\"
 
Write the note you would actually jot down for this part.
Style: {style}
 
Rules:
- Output ONLY the note. No preamble, no quotes, no explanation.
- Do not copy the professor's sentences word for word.
- Keep any equations or key terms you'd realistically write down.
- If this part has nothing worth writing down (small talk, greetings, mic/tech issues), output exactly: SKIP"""


# ------------------------------------------------------------
# Shared Helpers

def chunk_text(text, target_words=70):
    """Split a transcript into ~target_words chunks on sentence boundaries, no overlap.
    Ideally match whatever chunking the app itself uses at inference time."""
    text = re.sub(r"\s+", " ", text).strip()
    sents = []
    for s in re.split(r"(?<=[.!?])\s+", text):
        words = s.split()
        # unpunctuated runs (whisper sometimes does this) get split into word windows
        while len(words) > 2 * target_words:
            sents.append(" ".join(words[:target_words]))
            words = words[target_words:]
        if words:
            sents.append(" ".join(words))
 
    chunks, current, n = [], [], 0
    for s in sents:
        current.append(s)
        n += len(s.split())
        if n >= target_words:
            chunks.append(" ".join(current))
            current, n = [], 0
    if current:
        if chunks and n < target_words // 2:
            chunks[-1] += " " + " ".join(current)
        else:
            chunks.append(" ".join(current))
    return chunks


# Function used for testing/creating data
def add_typos(text, rng, rate=0.04):
    """Swap adjacent letters in a few words so notes look hand-typed."""
    out = []
    for w in text.split(" "):
        if len(w) > 3 and w.isalpha() and rng.random() < rate:
            i = rng.randrange(len(w) - 1)
            w = w[:i] + w[i + 1] + w[i] + w[i + 2:]
        out.append(w)
    return " ".join(out)

def clean_note(note):
    note = note.strip().strip('"').strip()
    note = re.sub(r"^(here('s| is) (my|the) note:?|note:)\s*", "", note, flags=re.I)
    return note.strip()

def load_rows(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def split_lectures(rows, test_frac, seed):
    lectures = sorted({r["lecture"] for r in rows})
    if len(lectures) < 2:
        raise SystemExit("Need at least 2 lectures so one can be held out for testing.")
    rng = random.Random(seed)
    rng.shuffle(lectures)
    n_test = max(1, round(len(lectures) * test_frac))
    return set(lectures[n_test:]), set(lectures[:n_test])


def chunk_table(rows):
    """chunk_id -> {lecture, idx, text, skip}. Includes SKIP (filler) chunks so they act as distractors."""
    table = {}
    for r in rows:
        c = table.setdefault(r["chunk_id"], {"lecture": r["lecture"], "idx": r["idx"],
                                             "text": r["chunk"], "skip": False})
        c["skip"] = c["skip"] or r["skip"]
    return table


# -------------------------------------
# Generate

def ollama_generate(host, model, prompt, temperature):
    import requests
    r = requests.post(f"{host}/api/generate", timeout=300, json={
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": temperature},
    })
    r.raise_for_status()
    return r.json()["response"]

def cmd_gen(a):
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
 
    # resume support: skip anything already generated
    done, skipped = set(), set()
    if out.exists():
        for r in load_rows(out):
            done.add((r["chunk_id"], r["k"]))
            if r["skip"]:
                skipped.add(r["chunk_id"])
 
    files = sorted(Path(a.transcripts).glob("*.txt"))
    if not files:
        raise SystemExit(f"No .txt transcripts found in {a.transcripts}")
 
    with out.open("a", encoding="utf-8") as f:
        for fp in files:
            chunks = chunk_text(fp.read_text(encoding="utf-8"), a.chunk_words)
            idxs = range(len(chunks))
            if a.max_chunks and len(chunks) > a.max_chunks:
                # random but repeatable, spread across the lecture; ids keep real positions
                idxs = sorted(random.Random(f"{a.seed}-{fp.stem}").sample(idxs, a.max_chunks))
            print(f"{fp.stem}: {len(chunks)} chunks, using {len(idxs)}")
            for i in idxs:
                chunk = chunks[i]
                cid = f"{fp.stem}::{i}"
                for k in range(a.notes_per_chunk):
                    if cid in skipped:
                        break
                    if (cid, k) in done:
                        continue
                    rng = random.Random(f"{a.seed}-{cid}-{k}")  # deterministic per sample
                    style = rng.choice(STYLES)
                    note = clean_note(ollama_generate(
                        a.host, a.model, PROMPT.format(chunk=chunk, style=style), a.temperature))
                    skip = note.upper().startswith("SKIP") or not note
                    if not skip and rng.random() < a.typo_prob:
                        note = add_typos(note, rng)
                    f.write(json.dumps({
                        "lecture": fp.stem, "chunk_id": cid, "idx": i, "chunk": chunk,
                        "k": k, "style": style, "note": "" if skip else note, "skip": skip,
                    }) + "\n")
                    f.flush()
                    # Filler words.
                    if skip:
                        skipped.add(cid)
                        break
    print(f"Done -> {out}")

# ----------------------------------------------------------------
# Training

# Picks a wrong answer for each training note so the model learns what not to match
def mine_negatives(model, train_rows, chunks, gap, margin, topk, rng):
    """For each note, pick a hard negative: a chunk from the SAME lecture, at least 'gap' chunks
    away from the true one, that the base model finds similar, but not suspiciously close to the
    positive's score (those are likely the professor repeating the same idea = false negatives)."""
    import numpy as np
 
    train_lectures = {r["lecture"] for r in train_rows}
    cids = [c for c, v in chunks.items() if v["lecture"] in train_lectures]
    cidx = {c: i for i, c in enumerate(cids)}
    by_lec = defaultdict(list)
    for c in cids:
        by_lec[chunks[c]["lecture"]].append(cidx[c])
 
    print("Mining hard negatives with the base model...")
    chunk_emb = model.encode([chunks[c]["text"] for c in cids], batch_size=64,
                             normalize_embeddings=True, show_progress_bar=True)
    note_emb = model.encode([r["note"] for r in train_rows], batch_size=64,
                            normalize_embeddings=True, show_progress_bar=True)
 
    negs = []
    for j, r in enumerate(train_rows):
        pos_sim = float(note_emb[j] @ chunk_emb[cidx[r["chunk_id"]]])
        cand = [c for c in by_lec[r["lecture"]] if abs(chunks[cids[c]]["idx"] - r["idx"]) >= gap]
        if not cand:  # tiny lecture: fall back to other lectures
            cand = [c for i_lec, lst in by_lec.items() if i_lec != r["lecture"] for c in lst]
        sims = chunk_emb[cand] @ note_emb[j]
        order = np.argsort(-sims)
        ok = [cand[o] for o in order if sims[o] < pos_sim - margin][:topk]
        negs.append(chunks[cids[rng.choice(ok) if ok else rng.choice(cand)]]["text"])
    return negs


def cmd_train(a):
    import torch
    from datasets import Dataset
    from sentence_transformers import (SentenceTransformer, SentenceTransformerTrainer,
                                       SentenceTransformerTrainingArguments, losses)
    from sentence_transformers.training_args import BatchSamplers
 
    rows = load_rows(a.pairs)
    train_lec, test_lec = split_lectures(rows, a.test_frac, a.seed)
    chunks = chunk_table(rows)
    train_rows = [r for r in rows if r["lecture"] in train_lec and not r["skip"]]
    print(f"Train lectures: {len(train_lec)}  Test lectures: {sorted(test_lec)}")
    print(f"Training pairs: {len(train_rows)}")
 
    model = SentenceTransformer(a.base)
    rng = random.Random(a.seed)
    negs = mine_negatives(model, train_rows, chunks, a.neg_gap, a.neg_margin, a.neg_topk, rng)
 
    ds = Dataset.from_dict({
        "anchor": [r["note"] for r in train_rows],
        "positive": [r["chunk"] for r in train_rows],
        "negative": negs,
    }).shuffle(seed=a.seed)
 
    args = SentenceTransformerTrainingArguments(
        output_dir=str(Path(a.out) / "checkpoints"),
        num_train_epochs=a.epochs,
        per_device_train_batch_size=a.batch_size,
        learning_rate=a.lr,
        warmup_ratio=0.1,
        fp16=torch.cuda.is_available(),
        # two notes per chunk + negatives that are other rows' positives -> keep duplicates
        # out of the same batch, otherwise in-batch negatives include false negatives
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        logging_steps=20,
        save_strategy="no",
        report_to="none",
        seed=a.seed,
    )
    trainer = SentenceTransformerTrainer(
        model=model, args=args, train_dataset=ds,
        loss=losses.MultipleNegativesRankingLoss(model),
    )
    trainer.train()
 
    model.save(a.out)
    Path(a.out, "split.json").write_text(json.dumps(
        {"base": a.base, "seed": a.seed, "test_frac": a.test_frac,
         "train": sorted(train_lec), "test": sorted(test_lec)}, indent=2))
    print(f"Saved -> {a.out}")

# --------------------------------------------------------------
# Evaluation

def retrieval_metrics(model, test_rows, chunks, test_lec):
    """Query = note, corpus = every chunk from the test lectures (filler included)."""
    from sentence_transformers.evaluation import InformationRetrievalEvaluator
    queries = {f"q{i}": r["note"] for i, r in enumerate(test_rows)}
    corpus = {c: v["text"] for c, v in chunks.items() if v["lecture"] in test_lec}
    relevant = {f"q{i}": {r["chunk_id"]} for i, r in enumerate(test_rows)}
    ev = InformationRetrievalEvaluator(queries, corpus, relevant, name="test",
                                       show_progress_bar=False)
    res = ev(model)
    want = ["accuracy@1", "accuracy@5", "mrr@10", "ndcg@10"]
    return {w: next(v for k, v in res.items() if k.endswith(w) and "cosine" in k) for w in want}
 
 
def missing_detection(model, test_rows, chunks, test_lec, miss_frac, trials, seed):
    """Simulates the real task. Per test lecture, a random `miss_frac` of note-worthy chunks get
    no note (the student 'missed' them); the rest get one of their generated notes. Each chunk is
    scored by its max cosine similarity to ANY note in that lecture. Low score = flagged missing."""
    import numpy as np
    from sklearn.metrics import precision_recall_curve, roc_auc_score
 
    notes_by_chunk = defaultdict(list)
    for r in test_rows:
        notes_by_chunk[r["chunk_id"]].append(r["note"])
 
    emb_cache = {}
 
    def emb(texts):
        new = [t for t in set(texts) if t not in emb_cache]
        if new:
            for t, e in zip(new, model.encode(new, batch_size=64, normalize_embeddings=True)):
                emb_cache[t] = e
        return np.stack([emb_cache[t] for t in texts])
 
    aucs, f1s, thrs = [], [], []
    for t in range(trials):
        rng = random.Random(seed + t)
        y, s = [], []
        for lec in sorted(test_lec):
            cids = [c for c in notes_by_chunk if chunks[c]["lecture"] == lec]
            if len(cids) < 4:
                continue
            missed = set(rng.sample(cids, max(1, round(len(cids) * miss_frac))))
            notes = [rng.choice(notes_by_chunk[c]) for c in cids if c not in missed]
            sim = emb([chunks[c]["text"] for c in cids]) @ emb(notes).T
            y += [int(c in missed) for c in cids]
            s += list(-sim.max(axis=1))  # higher = more likely missing
        y, s = np.array(y), np.array(s)
        aucs.append(roc_auc_score(y, s))
        p, r, th = precision_recall_curve(y, s)
        f1 = 2 * p * r / np.clip(p + r, 1e-9, None)
        best = int(np.argmax(f1[:-1]))
        f1s.append(f1[best])
        thrs.append(-th[best])  # back to a cosine similarity threshold
    return {"roc_auc": float(np.mean(aucs)), "best_f1": float(np.mean(f1s)),
            "sim_threshold": float(np.mean(thrs))}
 
 
def cmd_eval(a):
    from sentence_transformers import SentenceTransformer
 
    rows = load_rows(a.pairs)
    _, test_lec = split_lectures(rows, a.test_frac, a.seed)
    chunks = chunk_table(rows)
    test_rows = [r for r in rows if r["lecture"] in test_lec and not r["skip"]]
    print(f"Test lectures: {sorted(test_lec)}  ({len(test_rows)} notes)\n")
 
    results = {}
    for name in a.models:
        model = SentenceTransformer(name)
        res = retrieval_metrics(model, test_rows, chunks, test_lec)
        res.update(missing_detection(model, test_rows, chunks, test_lec,
                                     a.miss_frac, a.trials, a.seed))
        results[name] = res
 
    cols = ["accuracy@1", "accuracy@5", "mrr@10", "ndcg@10", "roc_auc", "best_f1", "sim_threshold"]
    w = max(len(n) for n in results) + 2
    print("model".ljust(w) + "".join(c.rjust(14) for c in cols))
    for n, res in results.items():
        print(n.ljust(w) + "".join(f"{res[c]:14.3f}" for c in cols))
 
    if a.out:
        Path(a.out).write_text(json.dumps(results, indent=2))
        print(f"\nSaved -> {a.out}")


# -----------------------------------------------
# Command Line Interface

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
 
    g = sub.add_parser("gen", help="generate synthetic notes with Ollama")
    g.add_argument("--transcripts", required=True, help="folder of .txt transcripts, one per lecture")
    g.add_argument("--out", default="data/pairs.jsonl")
    g.add_argument("--model", default="llama3.1:8b", help="Ollama model name")
    g.add_argument("--host", default="http://localhost:11434")
    g.add_argument("--chunk-words", type=int, default=70)
    g.add_argument("--notes-per-chunk", type=int, default=2)
    g.add_argument("--max-chunks", type=int, default=0,
                help="only use this many randomly picked chunks per lecture (0 = all)")
    g.add_argument("--temperature", type=float, default=0.9)
    g.add_argument("--typo-prob", type=float, default=0.3)
    g.add_argument("--seed", type=int, default=42)
 
    for name in ("train", "eval"):
        s = sub.add_parser(name)
        s.add_argument("--pairs", default="data/pairs.jsonl")
        s.add_argument("--test-frac", type=float, default=0.2)
        s.add_argument("--seed", type=int, default=42)
        if name == "train":
            s.add_argument("--base", default=DEFAULT_BASE)
            s.add_argument("--out", default="models/notes-matcher")
            s.add_argument("--epochs", type=int, default=3)
            s.add_argument("--batch-size", type=int, default=32)
            s.add_argument("--lr", type=float, default=2e-5)
            s.add_argument("--neg-gap", type=int, default=3, help="min chunk distance for negatives")
            s.add_argument("--neg-margin", type=float, default=0.05)
            s.add_argument("--neg-topk", type=int, default=5)
        else:
            s.add_argument("--models", nargs="+", required=True, help="base and fine-tuned paths/names")
            s.add_argument("--miss-frac", type=float, default=0.4)
            s.add_argument("--trials", type=int, default=5)
            s.add_argument("--out", default="results.json")
 
    a = p.parse_args()
    {"gen": cmd_gen, "train": cmd_train, "eval": cmd_eval}[a.cmd](a)
 
 
if __name__ == "__main__":
    main()
 