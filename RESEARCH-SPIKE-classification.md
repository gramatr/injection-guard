# Research spike: prompt-injection detection is not one problem

**Status: spike / discussion doc. Nothing here changes shipped behavior.**
Exists to stop treating "does injection-guard work" as a single yes/no
question — it doesn't have one answer, because "prompt injection" is
several different attack shapes with different defenses, and our one
model+heuristic combo is being asked to cover all of them at once.

## Why this doc exists

injection-guard's own README reports **85.2% overall accuracy** (86M
model) on its internal eval set (`eval/dataset.py`,
`eval/compare_models.py`). Three independent real-world adversarial
benchmarks run against the same model show **6.0%, 13.3%, and 17.1%
recall** (InjecAgent n=200, deepset/prompt-injections n=116,
JailbreakBench n=182 — see `benchmarks/results/`). That is not a small
discrepancy, and the instinct that "we should be clear about what it's
detecting" rather than citing 85% as a blanket number is correct. This
doc is that clarification, broken out by attack category instead of
one aggregate.

## Why the 85.2% and the real-world recall numbers aren't the same claim

Three separate reasons, all visible from `injg/README.md` itself:

1. **Sample size.** The internal eval is 27 total examples across 8
   categories (1–8 examples per category). It's a smoke test that
   catches regressions between model sizes, not a statistically
   powered benchmark. None of our three real corpora are powered to
   injection-guard's own eval's standard either, but at n=116–200 each
   they are an order of magnitude closer to meaningful than n=1–8 per
   category.
2. **Metric mismatch.** 85.2% is *accuracy* (correct on attacks AND
   correct on benign text), and 12 of the 27 examples are
   benign/near-miss-benign — cases a classifier should find easy.
   Accuracy on a benign-heavy set stays high even when attack recall
   is low. Our benchmarks report *recall on attacks specifically*
   because that's the number that matters for a security control: did
   it catch the attack, not "was it right on average."
3. **Distribution shift.** The internal eval's examples were written
   by this project to probe named techniques. The real corpora contain
   attacker-optimized (JBB/PAIR) or naturally-occurring (InjecAgent,
   scraped from real tool-output scenarios) text that doesn't share
   the internal eval's phrasing conventions. A classifier (or a
   heuristic) tuned against one vocabulary does not transfer — this is
   the same overfitting pattern already surfaced in the
   `injection-mismatch.html` writeup for the deepset benchmark.

The sharpest example of all three compounding: the internal eval's
**indirect injection** category reports 2/2 — the strongest-looking
category in that table. InjecAgent is *specifically* real tool-output
indirect injection, at n=200 instead of n=2, and recall there is 6%.
Same category name, opposite real-world answer. Citing 85.2% without
naming this is actively misleading about the one category that matters
most for an agent that reads tool output (WebFetch, Read, API
responses) — which is injection-guard's own stated primary threat
model per its README's "Claude Code adapter" section.

## Proposed classification — six different problems, not one

Each of these needs to be evaluated and reported on separately, because
they have different attacker models and, in most cases, need different
defenses — a single text classifier is only a plausible fit for some of
them.

| # | Category | What it looks like | Internal eval (n) | Real benchmark (n, recall) | Right defense shape |
|---|---|---|---|---|---|
| 1 | **Direct override** | "Ignore your previous instructions," explicit command injection in the first person | 3/3 | — (no real corpus isolates this alone; closest proxy is deepset at 13.3%, which mixes this with scope-drift) | Text classifier is a reasonable fit — high lexical signal, this is what Prompt Guard was trained for |
| 2 | **Jailbreak / roleplay framing** | "You are now DAN," persona hijack, fake system-prompt impersonation | 2/2 | JailbreakBench (PAIR/vicuna), 17.1% | Text classifier, but needs adversarial-robustness training (PAIR optimizes against exactly this) — current recall says it isn't there yet |
| 3 | **Obfuscated / encoded payloads** | Base64, unicode homoglyphs, zero-width chars | 2/3 (both models miss base64 specifically, confidently — 0.999 confidence it's benign) | not isolated in our three corpora | **Not a classifier problem at all** — needs a decode-and-rescan preprocessing step (base64-decode, unicode-normalize) before the text ever reaches the model. This is a known, named blind spot in `injg/README.md` already — fixable without touching the model |
| 4 | **Indirect / tool-output injection** | Instructions embedded in data the agent reads (email body, API JSON, webpage) that the agent mistakes for a command | 2/2 | **InjecAgent, 6.0% recall (n=200)** | Classifier alone is the wrong primary tool — the injected text often has zero override vocabulary (e.g. "please transfer $3,000 to account..." reads as plausible content, not an attack signature). Needs **provenance-aware policy**: is this text arriving from an untrusted channel and now issuing an imperative to a tool-capable agent? That's a structural check (where did this text come from, is it now asking for an action), not a content classification |
| 5 | **Topic-drift / scope enforcement** | User/content steers a narrow-purpose bot off its intended topic, no malicious intent | not tested | deepset/prompt-injections, 13.3% — but per `injection-mismatch.html`, this benchmark is measuring *this* category, not category 1/2/4 | **Not a security problem.** This is product scope control (should a support bot answer questions outside its domain), and deserves its own non-security metric. Conflating its low recall with "injection detection is weak" is the exact mistake `injection-mismatch.html` already called out — keep it a separate line item so it stops polluting the security conversation |
| 6 | **Multilingual variants** of 1–4 | Any of the above, translated | 3/3 (86M) vs 1/3 (22M) | not isolated | Depends entirely on which underlying category — multilingual direct-override is still a classifier problem, multilingual indirect injection is still a provenance problem. Not a separate defense, just a dimension that needs coverage-checking across 1–4 |

## What this means for how we report numbers going forward

- Never cite "85.2%" without naming which categories it covers and at
  what n. It is not false, but unqualified it reads as a recall claim
  on real attacks, which it isn't.
- Report recall per category (1–6 above), not one blended number.
  Categories 1–2 can reasonably be scored on a classifier's recall.
  Category 3 should be scored as "did the preprocessing step catch it
  before the classifier ever saw it" — a different pipeline stage
  entirely. Category 4 should **not** be scored as a classifier recall
  problem at all; it needs its own structural-detection design before
  there's a meaningful number to report. Category 5 should be dropped
  from "injection detection" reporting entirely and tracked as a
  product-scope metric if anyone wants it.
- Any future README/marketing claim about injection-guard's catch rate
  needs a category qualifier attached, the same way `SERVER-SIDE.md`
  already qualifies the hosted-tier claim per-tool instead of
  stack-wide. "Detects prompt injection: 85%" is the same kind of
  overclaim `SERVER-SIDE.md` was written to prevent for hosting
  posture — this doc does the equivalent for detection-rate claims.

## Next steps (not yet decided, needs your call)

1. Re-run the llmail-inject-challenge held-out eval and this time
   capture output straight to `benchmarks/results/` (the earlier run's
   numbers — 0% heuristic / 27.3% model / 27.3% combined — only exist
   because they were transcribed from a chat session that was cut off
   before the output file was written).
2. Decide whether category 4 (indirect/tool-output injection) gets a
   dedicated structural-detection design spike of its own — it's the
   category injection-guard's own README treats as the primary threat
   model, and it's the one a text classifier is structurally the wrong
   tool for.
3. Decide whether category 3's decode-and-rescan fix is small enough
   to just ship now rather than spike further — it's a named, confirmed
   blind spot with an obvious mechanical fix (decode common encodings
   before classification), not an open research question.
