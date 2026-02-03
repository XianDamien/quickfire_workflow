# Change: Remove ink field from evaluation outputs

## Why
Ink marking is no longer desired and complicates the evaluation schema and downstream consumers. The requested change is to remove all ink-related behavior from the pipeline and outputs.

## What Changes
- Remove the `ink` field from evaluation output schemas and JSON files.
- Remove ink propagation through annotators, gatekeeper, and batch outputs.
- Remove ink-specific constants and documentation references.

## Impact
- Affected specs: `core-evaluation-engine`, `workflow-orchestration`, `audio-annotation`
- Affected code: `scripts/annotators/*`, `scripts/gatekeeper/*`, `scripts/gemini_batch*.py`, `scripts/main.py`, `README.md`
- Related changes: supersedes `update-gatekeeper-marking` and `update-gemini-audio-ink-propagation`
