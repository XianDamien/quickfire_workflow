# Tasks: Add ASR Hotword Logging

**Change ID**: add-asr-hotword-logs

---

## Implementation Tasks

### Task 1: Add hotword logging to Qwen ASR

**File**: `scripts/asr/qwen.py`

**Changes**:
1. Add `_save_hotwords()` helper method to `QwenASRProvider`
2. Call hotword saving in `transcribe_and_save_with_segmentation()` after building context words
3. Output file: `2_qwen_asr_hotwords.json`

**Status**: [ ] Pending

---

### Task 2: Add hotword logging to FunASR

**File**: `scripts/asr/funasr.py`

**Changes**:
1. Add `_save_hotwords()` helper function
2. Call hotword saving in `_init_vocabulary()` after extracting vocabulary
3. Output file: `3_asr_timestamp_hotwords.json`

**Status**: [ ] Pending

---

### Task 3: Update documentation

**File**: `scripts/README.md`

**Changes**:
1. Add section documenting new hotword log files
2. Include schema and troubleshooting guidance

**Status**: [ ] Pending

---

### Task 4: Create spec delta

**File**: `openspec/changes/add-asr-hotword-logs/specs/asr-hotword-logging/spec.md`

**Changes**:
1. Define hotword logging requirements
2. Specify output schema

**Status**: [ ] Pending

---

## Verification

- [ ] Run Qwen ASR on test batch, verify `2_qwen_asr_hotwords.json` created
- [ ] Run FunASR on test batch, verify `3_asr_timestamp_hotwords.json` created
- [ ] Validate JSON schema matches specification
