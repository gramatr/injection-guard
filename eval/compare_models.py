"""
Runs eval/dataset.py against both Prompt Guard 2 sizes and reports
accuracy + latency PER CATEGORY, not aggregate-only — an aggregate
number can hide "catches direct override, misses every obfuscated
payload" the same way it nearly hid the 22M model's non-English-
specific weakness. Also answers the model-size question this eval
originally existed for.

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

CATEGORY_ORDER = [
    "direct_override",
    "jailbreak_roleplay",
    "fake_turn_markers",
    "obfuscated_encoded",
    "indirect_injection",
    "multilingual",
    "clean",
    "near_miss_benign",
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

    by_category = {}
    for case in CASES:
        by_category.setdefault(case["category"], []).append(case)

    overall_results = {}
    for model_id in MODELS:
        print(f"\n{'=' * 60}\n{model_id}\n{'=' * 60}")

        tok, model = load(model_id, token)

        total_correct = 0
        total_cases = 0
        all_latencies = []
        category_stats = {}

        for category in CATEGORY_ORDER:
            cases = by_category.get(category, [])
            if not cases:
                continue

            print(f"\n--- {category} ---")
            correct = 0
            latencies = []
            false_negatives = []
            false_positives = []

            for case in cases:
                predicted, score, elapsed_ms = classify(tok, model, case["text"])
                latencies.append(elapsed_ms)
                all_latencies.append(elapsed_ms)
                is_correct = predicted == case["expected"]
                correct += is_correct
                total_correct += is_correct
                total_cases += 1
                if not is_correct:
                    if case["expected"] and not predicted:
                        false_negatives.append(case["text"])
                    else:
                        false_positives.append(case["text"])
                status = "OK " if is_correct else "FAIL"
                print(f"  [{status}] expected={case['expected']!s:5} got={predicted!s:5} score={score:.3f} ({elapsed_ms:.1f}ms)  {case['text'][:55]!r}")

            avg_latency = sum(latencies) / len(latencies)
            category_stats[category] = {
                "cases": len(cases),
                "correct": correct,
                "fn": len(false_negatives),
                "fp": len(false_positives),
                "avg_latency_ms": avg_latency,
            }
            print(f"  {category}: {correct}/{len(cases)} correct, FN={len(false_negatives)}, FP={len(false_positives)}, avg_latency={avg_latency:.1f}ms")

        overall_accuracy = total_correct / total_cases
        overall_avg_latency = sum(all_latencies) / len(all_latencies)
        overall_results[model_id] = {
            "accuracy": overall_accuracy,
            "avg_latency_ms": overall_avg_latency,
            "category_stats": category_stats,
        }

    print(f"\n{'=' * 60}\nSummary — by category\n{'=' * 60}")
    header = f"{'category':<20}" + "".join(f"{m.split('/')[-1]:>22}" for m in MODELS)
    print(header)
    for category in CATEGORY_ORDER:
        if category not in overall_results[MODELS[0]]["category_stats"]:
            continue
        row = f"{category:<20}"
        for model_id in MODELS:
            s = overall_results[model_id]["category_stats"][category]
            row += f"{s['correct']}/{s['cases']} (FN={s['fn']},FP={s['fp']})".rjust(22)
        print(row)

    print(f"\n{'=' * 60}\nSummary — overall\n{'=' * 60}")
    for model_id, r in overall_results.items():
        print(f"{model_id}: accuracy={r['accuracy']:.1%}, avg_latency={r['avg_latency_ms']:.1f}ms")


if __name__ == "__main__":
    main()
