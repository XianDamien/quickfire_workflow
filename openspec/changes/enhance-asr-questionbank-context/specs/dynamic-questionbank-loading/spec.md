# Spec: Dynamic Questionbank Loading for ASR Context

## Why

Current ASR recognition has accuracy issues with domain-specific vocabulary:
- "all" misrecognized as "哦" (Cathy audio from R1-65-D5 questionbank)
- "升高" misrecognized as "身高" (Stefan audio from R3-14-D4 questionbank)

The existing `QwenASRProvider` class already supports questionbank-based context, but the `process_audio_file` function has faulty logic for loading the correct questionbank file based on the audio filename's progress code. Fixing this matching logic and ensuring context is properly passed to the ASR API should improve recognition accuracy for these specific vocabulary items.

## Overview
Enhance the Qwen ASR script to dynamically load and use questionbank files as recognition context based on audio filename, improving accuracy for domain-specific vocabulary.

## MODIFIED Requirements

### Requirement: Precise Questionbank File Matching
**ID**: qb-matching-precise

The system SHALL implement precise matching logic in `process_audio_file()` function to load the correct questionbank file based on the progress code extracted from the audio filename.

**Current Behavior**:
- Uses wildcard glob patterns that may match wrong files
- `progress_prefix` calculation is incorrect (removes only the last dash component)

**Desired Behavior**:
- System MUST try exact match first: find `{progress}.json` (e.g., `R1-65-D5.json`)
- System SHALL use `find_questionbank_file(progress)` as fallback if exact match fails
- System MUST log the loaded questionbank file name

**Validation**:
- Test files must be matched correctly:
  - `Zoe41900_2025-09-08_R1-65-D5_Cathy.mp3` → loads `questionbank/R1-65-D5.json`
  - `Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3` → loads `questionbank/R3-14-D4.json`

#### Scenario: Exact match with test audio
Given audio file `Zoe41900_2025-09-08_R1-65-D5_Cathy.mp3`
When parsing the filename extracts progress `R1-65-D5`
And questionbank file `questionbank/R1-65-D5.json` exists
Then the loader should select exactly this file
And log "📚 题库（精确匹配）: R1-65-D5.json"

#### Scenario: Exact match with another test audio
Given audio file `Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3`
When parsing the filename extracts progress `R3-14-D4`
And questionbank file `questionbank/R3-14-D4.json` exists
Then the loader should select exactly this file
And log "📚 题库（精确匹配）: R3-14-D4.json"

#### Scenario: Fallback to fuzzy match
Given audio file with unknown progress code that has no exact match
When questionbank file does not exist with exact name
Then the system should fallback to `find_questionbank_file(progress)`
And attempt fuzzy matching as secondary strategy

---

### Requirement: ASR Context Usage Verification
**ID**: asr-context-usage

The system SHALL ensure that the loaded questionbank file is passed to the ASR API as vocabulary context for recognition optimization.

**Current Behavior**:
- `vocabulary_path` parameter is already supported in `QwenASRProvider.transcribe_and_save_with_segmentation()`
- Context building is implemented in `QwenASRProvider.build_context_text()`

**Desired Behavior**:
- System MUST verify that `vocabulary_path` is passed correctly to ASR API
- System MUST log when context is being used (e.g., "📚 题库已作为上下文")
- System SHALL NOT silently fail if questionbank is found but context fails to load

#### Scenario: Questionbank passed as vocabulary context
Given a questionbank file is loaded
When calling `transcribe_and_save_with_segmentation()`
Then the `vocabulary_path` parameter must be set to the loaded questionbank file
And the ASR response should include context-based optimization

#### Scenario: Missing questionbank warning
Given audio file but no matching questionbank found
When `find_questionbank_file()` returns None
Then the system should log a warning: "⚠️  警告：未找到题库 (progress={progress})，ASR 将不使用上下文"
And continue processing without failing

---

### Requirement: Enhanced Logging for Debugging
**ID**: logging-enhancement

The system SHALL add detailed logging to track questionbank file loading and context usage.

**Current Behavior**:
- Minimal logging about questionbank loading

**Desired Behavior**:
- System MUST log the progress code extracted from filename
- System MUST log the questionbank file selected (exact or fallback match)
- System SHALL log whether context is being used or not
- System MUST log all steps for easier debugging

#### Scenario: Full logging output for successful load
Given processing `Zoe41900_2025-09-08_R1-65-D5_Cathy.mp3`
Then logs should show:
```
⟳ Cathy: 处理音频...
   📊 音频时长: XX.X 秒
   📚 题库（精确匹配）: R1-65-D5.json
   ▶️  无需分段，直接转写...
   ✓ Cathy: 已保存到 ...
```

#### Scenario: Logging when no questionbank found
Given processing audio with unmatched progress code
Then logs should show:
```
⟳ Student: 处理音频...
   ⚠️  警告：未找到题库 (progress=UNKNOWN)，ASR 将不使用上下文
   ▶️  直接转写...
```

---

## ADDED Requirements

### Requirement: Accuracy Test for Vocabulary Recognition
**ID**: vocab-recognition-test

The system SHALL validate that questionbank context improves recognition accuracy for specific vocabulary items.

**Test Cases**:
1. **Test Case 1**: Cathy audio with "all" vocabulary
   - Audio file: `backend_input/Zoe41900_2025-09-08_R1-65-D5_Cathy.mp3`
   - Expected: The word "all" MUST be correctly recognized
   - Not expected: "哦" (previously misrecognized)
   - Questionbank context: R1-65-D5.json (contains "all")

2. **Test Case 2**: Stefan audio with "升高" vocabulary
   - Audio file: `backend_input/Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3`
   - Expected: The word "升高" MUST be correctly recognized
   - Not expected: "身高" (previously misrecognized)
   - Questionbank context: R3-14-D4.json (contains "升高")

#### Scenario: Successful recognition with context - "all"
Given audio file `Zoe41900_2025-09-08_R1-65-D5_Cathy.mp3`
When processed with R1-65-D5 questionbank as context
Then the transcription result MUST contain "all"
And MUST NOT contain "哦" as a substitution
And the JSON output `2_qwen_asr.json` MUST be valid and include this word

#### Scenario: Successful recognition with context - "升高"
Given audio file `Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3`
When processed with R3-14-D4 questionbank as context
Then the transcription result MUST contain "升高"
And MUST NOT contain "身高" as a misrecognition
And the JSON output `2_qwen_asr.json` MUST be valid and include this word

---

## Implementation Notes

### Code Location
- **File**: `scripts/qwen_asr.py`
- **Function**: `process_audio_file()` (lines ~945-965)
- **Related Functions**:
  - `parse_audio_filename()` - extracts progress code
  - `find_questionbank_file()` - fallback matching
  - `QwenASRProvider.transcribe_and_save_with_segmentation()` - uses vocabulary_path

### Key Code Changes
1. Remove incorrect `progress_prefix` calculation
2. Implement exact match first
3. Add proper logging at each step
4. Ensure `vocabulary_path` is always set if file exists

### Testing Constraints
- Must use real audio files from `backend_input/` directory
- NO mock/synthetic data allowed
- Results must be verified by examining actual ASR output JSON
- No simulation of API responses
