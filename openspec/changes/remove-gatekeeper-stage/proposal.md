# Change: Remove gatekeeper stage from the pipeline

## Why
Gatekeeper currently adds extra flow complexity and has caused failures in strict runs. The request is to remove gatekeeper from the main pipeline, keep it as an optional standalone flow, and avoid passing anomaly fields into the annotator/model.

## Report
- `scripts/main.py` includes `gatekeeper` in `DAG_STAGES` and always executes it (`check_stage_complete` returns false), then injects `ink` into `annotator_kwargs`.
- `scripts/gatekeeper/*` implements anomaly checks and maps results to `InkMark`.
- Annotators accept `ink` via `AnnotatorInput` and include it in output JSON (e.g., `scripts/annotators/base.py`, `scripts/annotators/gemini.py`).
- Batch flows already hardcode `ink: normal` (`scripts/gemini_batch.py`, `scripts/gemini_batch_audio.py`).
- The current spec change `update-gatekeeper-marking` defines non-blocking gatekeeper behavior and the `ink` field expectation.

## Plan
1. Remove `gatekeeper` from pipeline execution (`DAG_STAGES`, CLI choices, and stage dispatch) and stop all gatekeeper logging/invocation in `scripts/main.py`.
2. Keep `ink` in outputs as a default `normal` value, but stop propagating `ink` into annotators/models from the pipeline.
3. Introduce a standalone gatekeeper flow (separate entry point or CLI flag) so it can be run independently when needed.
4. Update docs/usage text and run a real-audio pipeline to confirm cards complete without gatekeeper and outputs remain consistent.

## What Changes
- Gatekeeper stage is removed from the main pipeline flow.
- No gatekeeper-derived fields are passed into annotators or models.
- Output keeps `ink` with a default `normal` value.
- Gatekeeper remains available as a standalone flow.

## Impact
- Affected specs: `workflow-orchestration` (gatekeeper removal + standalone flow), `core-evaluation-engine` (default `ink` output)
- Affected code: `scripts/main.py`, `scripts/gatekeeper/*`, `scripts/annotators/*`, `scripts/gemini_batch*.py`
