from difflib import SequenceMatcher



BULLETS = "•·▪◦‣–-* "

# Cleaning of the text, removing bullet poitns ect
def clean(text):
    return text.lstrip(BULLETS).strip()

def similar(a, b):
    return SequenceMatcher(None, clean(a).lower(), clean(b).lower()).ratio()

def fmt_time(seconds):
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


# Sentence model for comparing notes to lecture content by meaning.
# Uses our fine-tuned matcher (training/train_matcher.py) if it's been trained,
# otherwise falls back to the base all-MiniLM-L6-v2.
from pathlib import Path
MODEL_PATH = Path(__file__).resolve().parents[2] / "training" / "models" / "notes-matcher"
MODEL_NAME = str(MODEL_PATH) if MODEL_PATH.exists() else "all-MiniLM-L6-v2"
_model = None

def get_model():
    global _model
    if _model is None:
        # imported here so the web app starts fast; the model only loads on first analysis
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def encode(texts):
    return get_model().encode(texts, convert_to_tensor=True)


def cos_sim(a, b):
    from sentence_transformers import util
    return util.cos_sim(a, b)