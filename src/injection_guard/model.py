"""
Loads Llama Prompt Guard 2 ONCE at process startup and classifies text as
benign or malicious (prompt injection / jailbreak attempt). Binary
classifier, no injection sub-labels (per Meta's model card).

512-token input limit — longer text is split into chunks and classified
independently; ANY chunk flagged malicious flags the whole input, same
"any match flags it" posture as secret-guard's redaction logic.
"""

import logging

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from injection_guard.config import MODEL_ID

logger = logging.getLogger("injection_guard")

_tokenizer = None
_model = None

MAX_TOKENS = 512
CHUNK_OVERLAP = 32  # avoid splitting an injection phrase exactly at a chunk boundary


def load_model() -> None:
    """Called once at daemon startup — this is the only place model weights
    are loaded. Never call this per-request."""
    global _tokenizer, _model
    if _model is not None:
        return
    logger.info("Loading %s (this happens once, not per request)", MODEL_ID)
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    _model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
    _model.eval()


def _classify_chunk(text: str) -> tuple[str, float]:
    inputs = _tokenizer(
        text, return_tensors="pt", truncation=True, max_length=MAX_TOKENS
    )
    with torch.no_grad():
        logits = _model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]
    pred_id = int(probs.argmax().item())
    label = _model.config.id2label[pred_id]
    score = float(probs[pred_id].item())
    return label, score


def classify(text: str) -> dict:
    """Returns {malicious: bool, label: str, score: float, chunks_scanned: int}.
    `label`/`score` describe the highest-confidence malicious chunk if any
    chunk was flagged, otherwise the first chunk's result."""
    if _model is None:
        raise RuntimeError("load_model() was not called before classify()")

    token_ids = _tokenizer(text, add_special_tokens=False)["input_ids"]
    if len(token_ids) <= MAX_TOKENS:
        chunks = [text]
    else:
        step = MAX_TOKENS - CHUNK_OVERLAP
        chunks = [
            _tokenizer.decode(token_ids[i : i + MAX_TOKENS])
            for i in range(0, len(token_ids), step)
        ]

    results = [_classify_chunk(chunk) for chunk in chunks]
    malicious_results = [r for r in results if r[0].upper() == "MALICIOUS"]

    if malicious_results:
        label, score = max(malicious_results, key=lambda r: r[1])
        return {
            "malicious": True,
            "label": label,
            "score": score,
            "chunks_scanned": len(chunks),
        }

    label, score = results[0]
    return {
        "malicious": False,
        "label": label,
        "score": score,
        "chunks_scanned": len(chunks),
    }
