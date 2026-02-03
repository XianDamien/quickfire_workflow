# Change: Update gemini-audio ink propagation

## Why
The pipeline now forwards gatekeeper `ink` to annotators, but the gemini-audio path errors out and stops strict runs. We need gemini-audio to accept and persist `ink` just like the text-based annotators.

## Report
- Observed failure: `GeminiAudioAnnotator.run_archive_student()` raises `unexpected keyword argument 'ink'`, which stops the cards stage in strict mode.
- Root cause: `scripts/annotators/gemini_audio.py` overrides `run_archive_student` without an `ink` parameter, while `scripts/main.py` always passes `ink` after gatekeeper.
- Output gap: gemini-audio output generation does not include the top-level `ink` field in `4_llm_annotation.json`, so anomalies are not persisted even if the call succeeds.
- Scope: only the gemini-audio annotator is affected; other annotators use the base implementation that already accepts and forwards `ink`.

## Plan
1. Align `GeminiAudioAnnotator.run_archive_student` with the base signature and pass `ink` into `AnnotatorInput` and error outputs.
2. Persist `ink` in gemini-audio output JSON to match the structured evaluation schema.
3. Run a real-audio pipeline check for a batch with gatekeeper anomalies and confirm `4_llm_annotation.json` contains the expected `ink` value.

## What Changes
- Accept and propagate `ink` in gemini-audio run flow.
- Include `ink` in sync-audio annotation output files.
- Verify the non-blocking gatekeeper + gemini-audio path end-to-end.

## Impact
- Affected specs: `audio-annotation`, `core-evaluation-engine`, `workflow-orchestration`
- Affected code: `scripts/annotators/gemini_audio.py`, `scripts/main.py`
