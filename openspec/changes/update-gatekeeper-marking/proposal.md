# Change: Update gatekeeper to ink-only anomalies

## Why
Gatekeeper currently blocks the pipeline on anomalies, but the desired behavior is to keep annotation running and only note anomalies for teacher review.

## What Changes
- Gatekeeper becomes a non-blocking anomaly marker (NOTED only affects `ink`, no FAIL semantics).
- Annotation output (`4_llm_annotation.json` and API response) includes a top-level `ink` field.
- `ink` values: `normal`, `wrong_questionbank`, `audio_anomaly`.
- The anomaly checker implementation is model-agnostic (not tied to Qwen).

## Impact
- Affected specs: `workflow-orchestration`, `core-evaluation-engine`
- Affected code: `scripts/main.py`, `scripts/gatekeeper/*`, `scripts/annotators/*`, `scripts/gemini_batch*.py`, API response builders
