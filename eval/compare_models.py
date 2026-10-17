"""
Runs the eval set (eval/dataset.py) against both Prompt Guard 2 sizes
and reports accuracy + per-classification latency, to answer a concrete
question: ship one size, or let the user choose?

Usage: uv run python eval/compare_models.py
Requires HF_TOKEN env var set to a token with the gated license accepted.
"""

import os
import time

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODELS = [
    "meta-llama/Llama-Prompt-Guard-2-86M",
    "meta-llama/Llama-Prompt-Guard-2-22M",
]


def load(model_id: str, token: str):
    tok = AutoTokenizer.from_pretrained(model_id, token=token)
    model = AutoModelForSequenceClassification.from_pretrained(model_id, token=token)
    model.eval()
    return tok, model


def classify(tok, model, text: str):
    # Index 0 = benign, index 1 = malicious — confirmed empirically against
    # both checkpoints. model.config.id2label is a generic LABEL_0/LABEL_1
    # placeholder, not usable as a string match. See src/injection_guard/model.py.
    inputs = tok(text, return_tensors="pt", truncation=True, max_length=512)
    start = time.perf_counter()
    with torch.no_grad():
        logits = model(**inputs).logits
    elapsed_ms = (time.perf_counter() - start) * 1000
    probs = torch.softmax(logits, dim=-1)[0]
    pred_id = int(probs.argmax().item())
    score = float(probs[pred_id].item())
    return pred_id == 1, score, elapsed_ms


def main():
    from dataset import CASES

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN env var required")

    results = {}
    for model_id in MODELS:
        print(f"\n=== {model_id} ===")
        tok, model = load(model_id, token)

        correct = 0
        latencies = []
        false_negatives = []
        false_positives = []

        for text, expected in CASES:
            predicted, score, elapsed_ms = classify(tok, model, text)
            latencies.append(elapsed_ms)
            is_correct = predicted == expected
            correct += is_correct
            if not is_correct:
                if expected and not predicted:
                    false_negatives.append(text)
                else:
                    false_positives.append(text)
            status = "OK " if is_correct else "FAIL"
            print(f"  [{status}] expected={expected!s:5} got={predicted!s:5} score={score:.3f} ({elapsed_ms:.1f}ms)  {text[:60]!r}")

        accuracy = correct / len(CASES)
        avg_latency = sum(latencies) / len(latencies)
        results[model_id] = {
            "accuracy": accuracy,
            "avg_latency_ms": avg_latency,
            "false_negatives": false_negatives,
            "false_positives": false_positives,
        }
        print(f"  accuracy={accuracy:.1%}  avg_latency={avg_latency:.1f}ms  "
              f"false_negatives={len(false_negatives)}  false_positives={len(false_positives)}")

    print("\n=== Summary ===")
    for model_id, r in results.items():
        print(f"{model_id}: accuracy={r['accuracy']:.1%}, avg_latency={r['avg_latency_ms']:.1f}ms, "
              f"FN={len(r['false_negatives'])}, FP={len(r['false_positives'])}")


if __name__ == "__main__":
    main()
