# Proposal: Remove Default Hotword Injection in Qwen ASR

**Change ID**: remove-hotword-default
**Status**: Proposed
**Created**: 2026-01-05
**Author**: Claude

---

## Why

Hotword injection in Qwen ASR causes forced language switching that corrupts mixed-language transcriptions. When English words appear in the audio, the ASR forces them to Chinese translations instead of preserving the original English. This breaks the downstream annotation pipeline which expects accurate transcriptions.

Real-world impact:
- Student says: "I like apples" (English)
- Current ASR output: "我喜欢苹果" (forced to Chinese)
- Expected output: "I like apples" (preserve original)

Removing default hotword injection:
1. Preserves natural mixed Chinese-English speech
2. Improves transcription accuracy for the actual use case
3. Simplifies code by removing unused optimization
4. Maintains audit trail with empty hotword metadata files

---

## Summary

Remove default hotword/vocabulary injection in Qwen ASR processing to preserve mixed-language (Chinese-English) output quality. Hotwords will still be logged for audit purposes, but will NOT be injected into the ASR API calls by default.

---

## Motivation

Current behavior injects hotwords from questionbank files into Qwen ASR API calls via the system context parameter. This was intended to improve recognition accuracy for domain-specific vocabulary. However, in practice:

1. **Language Mixing Issues** - Hotword injection causes the ASR to force Chinese translations of English words, corrupting the original mixed-language utterances
2. **Recognition Quality Degradation** - Instead of improving accuracy, hotwords introduce unwanted language-switching artifacts
3. **Poor Cost-Benefit** - The complexity of hotword extraction, hashing, and logging does not justify the degraded output quality

Example problematic behavior:
- Input audio: "I like apples" (English)
- With hotwords: ASR outputs "我喜欢苹果" (forced Chinese)
- Expected: "I like apples" (preserve original language)

---

## Scope

### In Scope

1. **Code Changes**:
   - Remove hotword injection from `QwenASRProvider.transcribe_audio()`
   - Remove hotword building from `transcribe_and_save()` and `transcribe_and_save_with_segmentation()`
   - Keep `_save_hotwords()` method but always save empty hotword lists
   - Keep `load_vocabulary()` and `build_context_words()` utility methods for potential future use
   - Update docstrings to clarify default behavior

2. **Archive Cleanup**:
   - Delete all existing `2_qwen_asr.json` files (139 files across all batches)
   - Delete all existing `2_qwen_asr_hotwords.json` files
   - Delete all existing `2_qwen_asr_no_hotwords.json` comparison files
   - Regenerate all ASR transcriptions without hotwords using updated scripts

3. **Documentation**:
   - Update `scripts/asr/qwen.py` docstrings
   - Update `scripts/README.md` to reflect new behavior
   - Update `CLAUDE.md` if ASR behavior is documented there

### Out of Scope

- FunASR hotword behavior (unchanged)
- Annotator pipeline changes
- Timestamp extraction changes
- Adding ability to explicitly enable hotwords via CLI flags (future enhancement if needed)

---

## Design

### Code Changes

#### Before (Current Behavior)

```python
# In transcribe_audio()
system_context = system_context_override or ""
if not system_context and vocabulary_path and os.path.exists(vocabulary_path):
    vocab = self.load_vocabulary(vocabulary_path)
    system_context = self.build_context_text(vocab)  # Injects hotwords

# In transcribe_and_save()
context_words: List[str] = []
if vocabulary_path and os.path.exists(vocabulary_path):
    vocab = self.load_vocabulary(vocabulary_path)
    context_words = self.build_context_words(vocab)  # Builds hotwords

response = self.transcribe_audio(
    system_context_override=", ".join(context_words) if context_words else None  # Injects
)
```

#### After (Proposed Behavior)

```python
# In transcribe_audio()
# Hotword context is disabled by default to preserve mixed-language output.
# Callers can still pass system_context_override explicitly if needed.
system_context = system_context_override or ""

# In transcribe_and_save()
context_words: List[str] = []  # Always empty, no hotword building

response = self.transcribe_audio(
    system_context_override=None  # Never inject hotwords
)
```

### Hotword Logging

Hotword metadata files will still be generated but will contain empty lists:

```json
{
  "vocabulary_path": "archive/Zoe41900_2025-09-08/_shared_context/R1-65.json",
  "hotwords": [],
  "count": 0,
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "created_at": "2026-01-05T12:00:00Z",
  "provider": "qwen3-asr",
  "model": "qwen3-asr-flash"
}
```

This preserves audit trail consistency while documenting that no hotwords were used.

### Archive Cleanup Strategy

Given 139+ Qwen ASR files across multiple batches, cleanup will be systematic:

1. **Identify all batches**:
   ```bash
   find archive -name "2_qwen_asr*.json" -exec dirname {} \; | sort -u
   ```

2. **Delete Qwen artifacts per batch**:
   ```bash
   find archive/<batch> -name "2_qwen_asr*.json" -delete
   ```

3. **Regenerate using updated scripts**:
   ```bash
   python3 scripts/main.py --archive-batch <batch> --only qwen_asr --force
   ```

4. **Verify output quality** - Compare new transcriptions to ensure mixed-language preservation

---

## Impact

### Modified Files

- `scripts/asr/qwen.py`:
  - `transcribe_audio()` - Remove hotword injection logic
  - `transcribe_and_save()` - Remove hotword building
  - `transcribe_and_save_with_segmentation()` - Remove hotword building
  - Docstrings - Update to clarify default behavior

- `scripts/README.md` - Document that Qwen ASR no longer uses hotwords by default

- Archive files (destructive):
  - Delete all `2_qwen_asr.json` (139 files)
  - Delete all `2_qwen_asr_hotwords.json`
  - Delete all `2_qwen_asr_no_hotwords.json`

### Unmodified Files

- `scripts/main.py` - No changes (already calls Qwen ASR correctly)
- `scripts/asr/funasr.py` - FunASR hotword behavior unchanged
- Annotator pipeline - Unchanged
- Timestamp extraction - Unchanged

### Behavioral Changes

| Aspect | Before | After |
|--------|--------|-------|
| ASR Input | Audio + vocabulary hotwords | Audio only (no hotwords) |
| System Context | Comma-separated word list | Empty or default message |
| Output Language | Mixed → Forced Chinese | Mixed → Preserved |
| Hotword Files | Non-empty hotword lists | Empty hotword lists |
| Recognition Quality | Degraded by language forcing | Natural mixed-language |

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Loss of domain-specific accuracy | Medium | Test on real audio to verify quality is actually better without hotwords |
| Breaking existing workflows | Low | Archive regeneration is idempotent; can re-run anytime |
| Need to re-enable hotwords later | Low | Code kept; can add `--use-hotwords` flag if needed |

---

## Acceptance Criteria

### Code Changes
- [ ] `QwenASRProvider.transcribe_audio()` never injects hotwords by default
- [ ] `transcribe_and_save()` does not build hotword lists
- [ ] `transcribe_and_save_with_segmentation()` does not build hotword lists
- [ ] `_save_hotwords()` always saves empty hotword lists
- [ ] Docstrings updated to reflect "default: no hotwords"
- [ ] Utility methods `load_vocabulary()` and `build_context_words()` preserved for future use

### Archive Cleanup
- [ ] All `2_qwen_asr.json` files deleted (139 files)
- [ ] All `2_qwen_asr_hotwords.json` files deleted
- [ ] All `2_qwen_asr_no_hotwords.json` files deleted
- [ ] All batches regenerated with new scripts
- [ ] Spot-check 3-5 transcriptions to verify mixed-language preservation

### Documentation
- [ ] `scripts/asr/qwen.py` docstrings updated
- [ ] `scripts/README.md` updated
- [ ] Git commit includes clear explanation of rationale

### Validation
- [ ] Run full pipeline on at least 1 batch end-to-end
- [ ] Verify no errors in ASR stage
- [ ] Verify annotation stage still works correctly
- [ ] Compare transcription quality: confirm no forced language switching

---

## Tasks

See `tasks.md` for detailed implementation steps.
