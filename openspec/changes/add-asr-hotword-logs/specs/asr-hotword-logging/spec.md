# Specification: ASR Hotword Logging

**Capability ID**: asr-hotword-logging
**Version**: 1.0
**Status**: Proposed
**Last Updated**: 2026-01-03

---

## Overview

ASR providers SHALL persist hotword/vocabulary metadata used during transcription to enable debugging, auditing, and reproducibility.

---

## ADDED Requirements

### Requirement: System SHALL Log Hotwords for Qwen ASR

The system SHALL save hotword metadata to `2_qwen_asr_hotwords.json` in the student output directory when performing Qwen ASR transcription.

**Trigger**: After `build_context_words()` in `QwenASRProvider.transcribe_and_save_with_segmentation()`

**Output Location**: `archive/<batch>/<student>/2_qwen_asr_hotwords.json`

#### Schema

```json
{
  "vocabulary_path": "string | null",
  "hotwords": ["string"],
  "count": "integer",
  "sha256": "string (64-char hex)",
  "created_at": "string (ISO 8601)",
  "provider": "qwen3-asr",
  "model": "string"
}
```

#### Scenario: Qwen ASR with Vocabulary

**Given**: Audio file and vocabulary path provided

**When**: `transcribe_and_save_with_segmentation()` executes

**Then**: Creates `2_qwen_asr_hotwords.json` with:
- `vocabulary_path`: Path to source questionbank
- `hotwords`: Sorted list of extracted words
- `count`: Number of unique hotwords
- `sha256`: Hash of comma-joined hotwords
- `created_at`: ISO timestamp
- `provider`: "qwen3-asr"
- `model`: Model name (e.g., "qwen3-asr-flash")

---

### Requirement: System SHALL Log Hotwords for FunASR

The system SHALL save hotword metadata to `3_asr_timestamp_hotwords.json` in the student output directory when performing FunASR transcription.

**Trigger**: After `extract_vocabulary()` in `FunASRTimestampProvider._init_vocabulary()`

**Output Location**: `archive/<batch>/<student>/3_asr_timestamp_hotwords.json`

#### Schema

```json
{
  "vocabulary_path": "string | null",
  "hotwords": [{"text": "string", "weight": "integer", "lang": "string"}],
  "count": "integer",
  "sha256": "string (64-char hex)",
  "created_at": "string (ISO 8601)",
  "provider": "fun-asr",
  "model": "string",
  "vocabulary_id": "string | null"
}
```

#### Scenario: FunASR with Vocabulary

**Given**: Audio file and vocabulary path provided

**When**: `transcribe_and_save()` executes with vocabulary

**Then**: Creates `3_asr_timestamp_hotwords.json` with:
- `vocabulary_path`: Path to source questionbank
- `hotwords`: List of hotword objects with text, weight, lang
- `count`: Number of unique hotwords
- `sha256`: Hash of hotwords JSON
- `created_at`: ISO timestamp
- `provider`: "fun-asr"
- `model`: Model name
- `vocabulary_id`: DashScope vocabulary slot ID

---

### Requirement: Hotword Logs SHALL Include Hash for Verification

Both hotword log files SHALL include a SHA-256 hash of the hotwords content to enable verification that the same vocabulary was used across runs.

**Hash Calculation**:
- Qwen ASR: `sha256(", ".join(sorted_hotwords))`
- FunASR: `sha256(json.dumps(hotwords, sort_keys=True))`

---

## File Naming Convention

| Stage | File Name | Provider |
|-------|-----------|----------|
| 2 | `2_qwen_asr_hotwords.json` | Qwen ASR |
| 3 | `3_asr_timestamp_hotwords.json` | FunASR |

---

## Related Specifications

- **audio-transcription**: Parent spec defining ASR behavior
- **workflow-orchestration**: Orchestrates ASR stages
