# Proposal: Add ASR Hotword Logging

**Change ID**: add-asr-hotword-logs
**Status**: Proposed
**Created**: 2026-01-03
**Author**: Claude

---

## Summary

Add hotword/vocabulary logging to ASR processing pipeline. Both Qwen ASR and FunASR will save the hotwords used during transcription for debugging, auditing, and reproducibility purposes.

---

## Motivation

Currently, ASR providers (Qwen and FunASR) use hotwords from questionbank files to improve recognition accuracy, but the actual hotwords used are not persisted. This makes it difficult to:

1. **Debug** - Verify which hotwords were actually loaded for a specific transcription
2. **Audit** - Track changes in vocabulary over time
3. **Reproduce** - Recreate exact transcription conditions

---

## Scope

### In Scope

- Save hotword metadata to `2_qwen_asr_hotwords.json` for Qwen ASR
- Save hotword metadata to `3_asr_timestamp_hotwords.json` for FunASR
- Include vocabulary source path, word list, count, hash, and timestamps

### Out of Scope

- Modifying hotword extraction logic
- Changing ASR transcription behavior
- Adding new ASR providers

---

## Design

### Output File Format

Both files will share a common schema:

```json
{
  "vocabulary_path": "archive/<batch>/_shared_context/<questionbank>.json",
  "hotwords": ["word1", "word2", "word3"],
  "count": 42,
  "sha256": "abc123...",
  "created_at": "2026-01-03T10:00:00Z",
  "provider": "qwen3-asr" | "fun-asr",
  "model": "qwen3-asr-flash" | "fun-asr"
}
```

### Output Locations

| Provider | Output File | Directory |
|----------|-------------|-----------|
| Qwen ASR | `2_qwen_asr_hotwords.json` | `archive/<batch>/<student>/` |
| FunASR | `3_asr_timestamp_hotwords.json` | `archive/<batch>/<student>/` |

### Trigger Points

- **Qwen ASR**: After `build_context_words()` in `transcribe_and_save_with_segmentation()`
- **FunASR**: After `extract_vocabulary()` / `_init_vocabulary()` in `transcribe_and_save()`

---

## Impact

### Modified Files

- `scripts/asr/qwen.py` - Add hotword saving logic
- `scripts/asr/funasr.py` - Add hotword saving logic
- `scripts/README.md` - Document new output files

### Spec Updates

- `openspec/specs/audio-transcription/spec.md` (if exists) or create new spec

---

## Acceptance Criteria

- [ ] Qwen ASR creates `2_qwen_asr_hotwords.json` with correct schema
- [ ] FunASR creates `3_asr_timestamp_hotwords.json` with correct schema
- [ ] Both files include all required metadata fields
- [ ] Documentation updated in scripts/README.md
