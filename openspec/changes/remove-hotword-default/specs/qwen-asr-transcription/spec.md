# Spec: Qwen ASR Transcription

**Capability**: qwen-asr-transcription
**Change**: remove-hotword-default

---

## MODIFIED Requirements

### System SHALL transcribe audio without hotword injection by default

**Priority**: P0
**Category**: Core Functionality

Qwen ASR provider must transcribe audio files without injecting questionbank vocabulary as hotwords in the system context by default. This preserves the natural mixed-language (Chinese-English) output from the audio.

**Rationale**:
- Hotword injection causes forced language switching (e.g., English words get translated to Chinese)
- Mixed-language preservation is critical for accurate downstream annotation
- Domain vocabulary does not improve recognition quality in practice

#### Scenario: User runs ASR on mixed-language audio

**Given**:
- Audio file contains mixed Chinese and English: "I like apples 我喜欢苹果"
- Questionbank file exists at `archive/<batch>/_shared_context/R1-65.json`
- Questionbank contains vocabulary entries with English and Chinese words

**When**:
- User runs: `python3 scripts/main.py --archive-batch <batch> --student <name> --only qwen_asr`

**Then**:
- ASR transcribes audio preserving original language mixing
- Output contains: "I like apples 我喜欢苹果" (not forced to all Chinese or all English)
- No vocabulary hotwords are injected into Qwen API call
- `2_qwen_asr_hotwords.json` created with empty hotword list

**Verification**:
```bash
# Check transcription output
jq -r '.output.choices[0].message.content[0].text' archive/<batch>/<student>/2_qwen_asr.json

# Check hotword metadata
jq '.hotwords | length' archive/<batch>/<student>/2_qwen_asr_hotwords.json
# Expected: 0
```

---

#### Scenario: User can still override with explicit hotwords if needed

**Given**:
- Custom code calls `QwenASRProvider.transcribe_audio()` directly
- Caller wants to inject custom system context for testing

**When**:
- Caller passes `system_context_override="custom, hotwords, here"`

**Then**:
- ASR API receives the custom system context
- Transcription uses the provided hotwords
- Default hotword building is bypassed

**Verification**:
```python
provider = QwenASRProvider()
result = provider.transcribe_audio(
    audio_path="test.mp3",
    system_context_override="apple, banana, orange"
)
# Verify API call includes custom context
```

---

### System SHALL log empty hotword metadata for audit trail

**Priority**: P1
**Category**: Observability

Even when no hotwords are used, Qwen ASR must generate `2_qwen_asr_hotwords.json` with empty hotword lists to maintain consistent audit trail format.

**Rationale**:
- Downstream tools may expect hotword metadata files to exist
- Empty metadata documents "no hotwords used" explicitly
- Maintains consistency with historical logging behavior

#### Scenario: ASR completes without hotwords

**Given**:
- Qwen ASR transcribes audio file successfully
- No hotwords were injected (default behavior)

**When**:
- Transcription completes

**Then**:
- `2_qwen_asr_hotwords.json` is created in student directory
- File contains:
  - `"vocabulary_path"`: path to questionbank (if provided) or `null`
  - `"hotwords"`: empty array `[]`
  - `"count"`: `0`
  - `"sha256"`: hash of empty string
  - `"created_at"`: ISO timestamp
  - `"provider"`: `"qwen3-asr"`
  - `"model"`: `"qwen3-asr-flash"`

**Verification**:
```bash
# Verify file exists
test -f archive/<batch>/<student>/2_qwen_asr_hotwords.json

# Verify schema
jq '{
  has_vocabulary_path: has("vocabulary_path"),
  hotwords_empty: (.hotwords | length == 0),
  count_zero: (.count == 0),
  has_sha256: has("sha256"),
  has_timestamp: has("created_at"),
  provider_correct: (.provider == "qwen3-asr")
}' archive/<batch>/<student>/2_qwen_asr_hotwords.json

# Expected output:
# {
#   "has_vocabulary_path": true,
#   "hotwords_empty": true,
#   "count_zero": true,
#   "has_sha256": true,
#   "has_timestamp": true,
#   "provider_correct": true
# }
```

---

## REMOVED Requirements

### ~~Qwen ASR SHALL inject questionbank vocabulary as hotwords~~ (REMOVED)

**Removed in**: remove-hotword-default
**Reason**: Hotword injection degrades mixed-language transcription quality

This requirement previously specified:
- Loading vocabulary from questionbank JSON files
- Extracting English and Chinese words as hotwords
- Building comma-separated hotword lists
- Injecting hotwords into Qwen API via system context

**Migration Path**:
- Code for vocabulary loading preserved in `load_vocabulary()` and `build_context_words()`
- Callers can explicitly pass `system_context_override` if needed
- Default behavior changed to no hotword injection

---

### ~~Qwen ASR SHALL optimize recognition using domain vocabulary~~ (REMOVED)

**Removed in**: remove-hotword-default
**Reason**: Domain vocabulary did not improve recognition quality in practice; caused language-forcing issues

This requirement previously specified:
- Using questionbank vocabulary to improve ASR accuracy for domain-specific terms
- Expected benefit: Better recognition of student names, English words, etc.

**Actual Behavior Observed**:
- Hotwords caused forced language switching
- Mixed-language utterances corrupted
- No measurable improvement in recognition accuracy

**Migration Path**:
- Rely on Qwen ASR's built-in language detection
- Trust model to preserve natural language mixing
- Re-evaluate if specific domain vocabulary proves necessary in future

---

## ADDED Requirements

### System MUST preserve data integrity during archive regeneration

**Priority**: P0
**Category**: Data Management

When regenerating ASR transcriptions after removing hotword injection, the process must preserve all other archive data and maintain referential integrity.

**Rationale**:
- Archive contains 139+ ASR files across multiple batches
- Other pipeline stages (timestamps, annotations) depend on ASR output format
- Data loss or corruption would require significant recovery effort

#### Scenario: Regenerate all batches after code change

**Given**:
- All existing `2_qwen_asr*.json` files deleted
- Updated Qwen ASR code deployed (no hotword injection)
- All batches have valid `1_input_audio.*` files

**When**:
- User runs regeneration for all batches:
  ```bash
  for batch in $(ls archive/ | grep -E "^[A-Z].*_2025-"); do
    python3 scripts/main.py --archive-batch "$batch" --only qwen_asr --force
  done
  ```

**Then**:
- Each student directory has new `2_qwen_asr.json`
- Each student directory has new `2_qwen_asr_hotwords.json` (empty hotwords)
- Other files unchanged:
  - `1_input_audio.*` intact
  - `3_asr_timestamp.json` intact (if exists)
  - `4_llm_annotation.json` intact (if exists)
  - `runs/` directory intact (if exists)
- No duplicate or orphaned files created
- Full pipeline still runs end-to-end without errors

**Verification**:
```bash
# Count regenerated ASR files
find archive -name "2_qwen_asr.json" | wc -l
# Should match number of students across all batches

# Verify other files intact
find archive -name "1_input_audio.*" | wc -l  # Unchanged
find archive -name "3_asr_timestamp.json" | wc -l  # Unchanged

# Test full pipeline on sample
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --student Oscar --force
# Should complete all stages without errors
```

---

#### Scenario: Spot-check verifies quality improvement

**Given**:
- ASR regeneration complete for all batches
- Sample of 5 random transcriptions selected

**When**:
- Developer inspects transcribed text:
  ```bash
  find archive -name "2_qwen_asr.json" | shuf | head -5 | while read f; do
    echo "File: $f"
    jq -r '.output.choices[0].message.content[0].text' "$f"
    echo "---"
  done
  ```

**Then**:
- Mixed-language content preserved (no forced Chinese for English words)
- No obvious transcription errors introduced by hotword removal
- Quality appears equal or better than previous version

**Verification**:
- Manual inspection confirms natural language mixing
- No regression in transcription accuracy observed
- Developer approves quality before finalizing change

---

## Dependencies

### Internal Dependencies
- **scripts/common/archive.py**: `resolve_question_bank()` for finding vocabulary files
- **scripts/main.py**: Orchestrates `--only qwen_asr` pipeline stage
- **dashscope SDK**: Qwen API client for transcription

### External Dependencies
- **Qwen3-ASR API**: Must support transcription without system context (verified working)
- **Archive structure**: Expects `archive/<batch>/<student>/` layout

### Downstream Consumers
- **FunASR Timestamp Provider**: Reads `2_qwen_asr.json` for text input (format unchanged)
- **Annotators**: Read `2_qwen_asr.json` for transcribed text (format unchanged)
- **Reports**: May read hotword metadata for debugging (schema unchanged, just empty lists)

---

## Non-Functional Requirements

### Performance
- ASR transcription time unchanged (hotword building was negligible overhead)
- Regeneration of 139 files estimated at ~2-3 hours (depends on batch sizes)

### Maintainability
- Vocabulary utility methods preserved for potential future use
- Clear comments document why hotwords are disabled by default
- OpenSpec change documents migration path

### Compatibility
- Output JSON format unchanged (same Qwen API response structure)
- Hotword metadata schema unchanged (just contains empty lists)
- Downstream pipeline stages require no code changes

---

## Testing Strategy

### Unit Tests (Future)
- Test `transcribe_audio()` with and without `system_context_override`
- Verify `_save_hotwords()` generates correct schema with empty lists
- Test `load_vocabulary()` and `build_context_words()` still work (for future use)

### Integration Tests
- Full pipeline test: `audio → qwen_asr → timestamps → cards`
- Verify no errors in any stage
- Confirm annotation stage produces valid JSON

### Manual Testing
- Regenerate all 139 ASR files
- Spot-check 5 random transcriptions for quality
- Run end-to-end on representative batch

### Regression Prevention
- Document expected behavior in this spec
- Include test case for mixed-language preservation
- Monitor for language-forcing issues in future transcriptions

---

## Migration Notes

### For Developers
- If you need hotwords for testing, use `system_context_override` parameter directly
- Vocabulary loading code still exists in `load_vocabulary()` and `build_context_words()`
- Consider adding `--use-hotwords` CLI flag if there's demand for optional hotword injection

### For Operators
- All existing ASR files will be deleted and regenerated
- Process is idempotent - can re-run if needed
- Backup archive before starting if you want to preserve old transcriptions

### For Future Enhancements
- Could add hotword support back as opt-in via CLI flag
- Could implement selective hotword injection (only for specific words)
- Could experiment with different context formats (structured vs. word list)
