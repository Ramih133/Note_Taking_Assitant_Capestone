# Note Taking Assistant (Note AI)

Finds what's missing from a student's lecture notes. It transcribes the lecture live, compares
the transcript and slides against the notes with a fine-tuned sentence-transformer, and flags
important content the notes don't cover.

## Features
- **Live lecture mode**: records the mic, transcribes 15-second chunks with faster-whisper, and
  re-checks the notes for gaps while the lecture is going
- **Analyze my notes**: after the lecture, compares slides + recording/transcript + notes and
  lists missed points, a coverage score and recaps of missed sections
- **Define / Explain / Example**: highlight a term in your notes and get an explanation based on
  that lecture
- **Practice quizzes and flashcards**: multiple choice from the lecture, missed points first
- **Course page**: key terms and "this will be on the exam" moments from every lecture, each
  linked to the lines in your notes that cover it (or marked as missing)

## Models
| Job | Model |
|---|---|
| Note ↔ lecture matching | `notes-matcher`: all-MiniLM-L6-v2 fine-tuned on 11,203 synthetic note/lecture pairs (`training/`) |
| Live transcription | faster-whisper `small.en` (GPU), `base.en` (CPU fallback) |
| Upload transcription | faster-whisper `small` |
| Define, quizzes, recaps, key terms | Qwen2.5-1.5B-Instruct (local) |

Fine-tuning results on 61 held-out lectures (`training/results.json`):

| Metric | Base MiniLM | Fine-tuned |
|---|---|---|
| Accuracy@1 | 77.0% | 89.1% |
| Accuracy@5 | 92.7% | 97.7% |
| ROC-AUC (covered vs. missing) | 0.840 | 0.909 |
| Best F1 | 0.724 | 0.800 |

## Setup (Windows, Python 3.12)
Needs [FFmpeg](https://ffmpeg.org/) on PATH. An NVIDIA GPU is recommended; everything falls back to CPU.

```powershell
git clone https://github.com/Ramih133/Note_Taking_Assitant_Capestone.git
cd Note_Taking_Assitant_Capestone\app
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu126   # GPU; skip for CPU
pip install -r requirements.txt
```

## Run
```powershell
cd app
.venv\Scripts\activate
uvicorn app:app --reload
```
Open http://127.0.0.1:8000, create an account, then a class and a note. The first Whisper and
Qwen runs download the models, so they're slow once.

No mic? In a note's lecture panel, import a transcript instead, e.g. `data/rome_test/transcript.txt`.

## Evaluation
```powershell
python experiments\evaluate.py data\rome_test --show
python experiments\evaluate.py data\calculus_test --show
```
Real lecture transcripts with lines deliberately removed from the notes (`answer_key.txt`).

## Retraining the matcher
See `training/train_matcher.py` (`gen` → `train` → `eval`). Always retrain from the base model
when lectures are added. The trained model in `training/models/notes-matcher` is committed.

## Layout
```
app/              FastAPI web app (app.py, database.py, templates/, static/)
app/analysis/     pipeline: transcription, gap detection, define, quizzes, key terms
training/         matcher fine-tuning scripts, data and trained model
experiments/      evaluation script + results (Rome, Calculus)
data/             test lectures (Rome, Calculus) with notes and answer keys
docs/             sprint submissions
```
