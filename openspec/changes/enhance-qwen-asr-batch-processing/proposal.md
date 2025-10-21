# OpenSpec Proposal: Enhance Qwen ASR Batch Processing

**Change ID**: `enhance-qwen-asr-batch-processing`

**Author**: Claude Code

**Date**: 2025-10-21

**Status**: Draft

## Overview

Enhance the Qwen ASR provider (`scripts/qwen_asr.py`) to support batch transcription with command-line interface for processing entire student datasets. This enables efficient bulk audio transcription across multiple homework submissions with automatic deduplication (skip if `2_qwen_asr.json` already exists).

## Problem Statement

Currently, `scripts/qwen_asr.py` has a batch processing function (`process_all_students()`) but lacks a user-friendly command-line interface for:
- Selective dataset processing (e.g., `--Zoe51530-9.8` or `--Oscar`)
- Transparent progress tracking and error handling
- Idempotent transcription (skip files already processed)

## Proposed Solution

Add a CLI layer to the Qwen ASR provider that:
1. Accepts dataset specification via command-line flags (e.g., `python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Oscar`)
2. Processes all student audio files in a specified dataset directory
3. Outputs standardized `2_qwen_asr.json` files
4. Skips already-processed files automatically (idempotent)
5. Provides clear progress reporting

## Scope

### In Scope
- Add CLI argument parser to `scripts/qwen_asr.py`
- Support `--dataset` flag for specifying datasets (e.g., Zoe51530-9.8, Zoe41900-9.8)
- Support `--student` flag for processing specific students
- Implement deduplication logic (check for existing `2_qwen_asr.json`)
- Progress reporting with student count and skip status
- Map `homework_submission/<DATASET>` → student audio files

### Out of Scope
- Changes to API key management (still via environment variable)
- Refactoring of ASR provider class
- Support for other ASR engines (FunASR, etc.)
- Modifying vocabulary file handling

## User-Facing Changes

### Command-Line Interface

```bash
# Process single student
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Oscar

# Process all students in dataset
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8

# Process all datasets and students
python3 scripts/qwen_asr.py

# Show help
python3 scripts/qwen_asr.py --help
```

### Output Behavior
- Creates `2_qwen_asr.json` in each student's directory
- Skips students that already have `2_qwen_asr.json`
- Prints progress: `✓ StudentName: Already processed (skipping)` or `✓ StudentName: Saved to 2_qwen_asr.json`

## Technical Design

See `design.md` for architectural details.

## Specifications

One main capability with clear requirements:

- **Qwen ASR Batch Transcription Interface** (`specs/qwen-asr-batch-transcription/spec.md`)
  - CLI argument parsing and dataset discovery
  - Batch processing workflow
  - Deduplication logic
  - Output file naming and structure

## Implementation Plan

See `tasks.md` for ordered, verifiable work items.

## Success Criteria

- ✅ CLI accepts `--dataset` and `--student` flags
- ✅ Skips files where `2_qwen_asr.json` already exists
- ✅ Outputs valid JSON matching ASR schema
- ✅ All existing functionality preserved (backward compatible)
- ✅ Clear progress reporting in logs
- ✅ No API changes to `QwenASRProvider` class

## Testing Plan

1. **Unit Tests**:
   - Dataset discovery from `homework_submission/` directory
   - Deduplication logic (existing file detection)

2. **Integration Tests**:
   - Single dataset, all students processing
   - Single student processing
   - Skipping already-processed files

3. **Manual Testing**:
   - Test with `--Zoe51530-9.8 --Oscar` flags
   - Verify output `2_qwen_asr.json` format
   - Check API quota and error handling

## Dependencies

- No new external dependencies required
- Uses existing `QwenASRProvider` class
- Relies on filesystem structure: `homework_submission/<DATASET>/<STUDENT>/`

## References

- **Related code**: `scripts/qwen_asr.py` (existing batch processing function)
- **Data structure**: `homework_submission/Zoe51530/9.8/` (example dataset)
- **Output format**: `2_qwen_asr.json` (standardized ASR result file)

## Rollback Plan

- No database changes or migrations
- Simply revert CLI argument parsing in `main()` function
- Existing `process_all_students()` remains functional as fallback
