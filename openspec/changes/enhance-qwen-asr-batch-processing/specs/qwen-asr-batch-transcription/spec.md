# Specification: Qwen ASR Batch Transcription Interface

**Capability**: Qwen ASR Batch Transcription Interface

**Version**: 1.0

**Status**: Draft

## Overview

This specification defines the command-line interface and batch processing workflow for the Qwen ASR transcription tool. It enables users to selectively transcribe student audio files across homework datasets with idempotent output (automatic skipping of already-processed files).

---

## ADDED Requirements

### Requirement: CLI Argument Interface

The `scripts/qwen_asr.py` script SHALL accept command-line arguments to control dataset and student selection for batch transcription operations. The system MUST support flexible dataset and student targeting while maintaining backward compatibility with the default all-in-one processing mode.

#### Scenario: Default Batch Processing
**Given**: User runs `python3 scripts/qwen_asr.py` with no arguments
**And**: DASHSCOPE_API_KEY environment variable is set
**When**: The script executes
**Then**:
- It processes all students in all datasets under `homework_submission/`
- For each student, it checks if `2_qwen_asr.json` already exists
- If file exists, it prints: `✓ StudentName: Already processed (skipping)`
- If file doesn't exist, it transcribes the audio and saves to `2_qwen_asr.json`
- It prints a summary: `Processed: N, Skipped: M`
- Exit code is 0

#### Scenario: Dataset Filtering
**Given**: User runs `python3 scripts/qwen_asr.py --dataset Zoe51530-9.8`
**And**: DASHSCOPE_API_KEY environment variable is set
**When**: The script executes
**Then**:
- It processes only students in `homework_submission/Zoe51530/9.8/`
- For each student, it checks for existing `2_qwen_asr.json`
- Skips or processes based on file existence
- It prints progress for each student in the dataset
- Exit code is 0

#### Scenario: Single Student Processing
**Given**: User runs `python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Oscar`
**And**: DASHSCOPE_API_KEY environment variable is set
**When**: The script executes
**Then**:
- It processes only the student named `Oscar` in dataset `Zoe51530-9.8`
- It checks if `homework_submission/Zoe51530/9.8/Oscar/2_qwen_asr.json` exists
- If exists, it prints skip message
- If not exists, it transcribes and saves to the location
- Exit code is 0

---

### Requirement: Audio File Discovery

The system SHALL automatically discover and prioritize student audio files within each student's directory, supporting multiple formats and naming conventions.

#### Scenario: Standard Audio File Naming
**Given**: Student directory contains `1_input_audio.mp3`
**When**: The system searches for audio files
**Then**:
- It uses `1_input_audio.mp3` for transcription
- It ignores other audio files in the directory
- No warning messages are printed

#### Scenario: Fallback Audio File Detection
**Given**: Student directory does not contain `1_input_audio.*` but contains `Oscar.mp3`
**And**: Student name is `Oscar`
**When**: The system searches for audio files
**Then**:
- It uses `Oscar.mp3` for transcription
- It ignores other files

#### Scenario: Multiple Audio Files with No Standard Naming
**Given**: Student directory contains multiple audio files with no standard naming
**When**: The system searches for audio files
**Then**:
- It uses the first audio file found (by filesystem order)
- It prints a warning: `⚠️ Multiple audio files found, using: filename.mp3`

#### Scenario: No Audio Files Found
**Given**: Student directory contains no audio files
**When**: The system processes the student
**Then**:
- It prints: `⊘ StudentName: No audio file found`
- Total skipped count is incremented
- Processing continues to next student

---

### Requirement: Deduplication Logic

The system SHALL check for existing output files and skip transcription operations for students whose audio has already been processed, ensuring idempotent behavior and efficient API usage.

#### Scenario: File Already Exists
**Given**: Student directory contains `2_qwen_asr.json`
**When**: The system processes the student
**Then**:
- It skips transcription
- It prints: `✓ StudentName: Already processed (skipping)`
- Skipped count is incremented
- Processing continues to next student
- No API call is made

#### Scenario: File Does Not Exist
**Given**: Student directory does not contain `2_qwen_asr.json`
**And**: Audio file exists (e.g., `1_input_audio.mp3`)
**When**: The system processes the student
**Then**:
- It invokes `QwenASRProvider.transcribe_and_save()`
- It saves output to `2_qwen_asr.json` in student directory
- It prints: `✓ StudentName: Saved to 2_qwen_asr.json`
- Processed count is incremented

---

### Requirement: Output File Naming and Format

All transcription outputs SHALL be saved as `2_qwen_asr.json` in the student directory with standardized JSON structure matching the Qwen ASR API response format.

#### Scenario: Output File Location
**Given**: Processing student `Oscar` in dataset `Zoe51530-9.8`
**When**: Transcription completes successfully
**Then**:
- Output file is saved to: `homework_submission/Zoe51530/9.8/Oscar/2_qwen_asr.json`
- File is valid JSON (parseable by `json.load()`)
- File permissions are readable and writable

#### Scenario: Output JSON Structure
**Given**: Transcription result from Qwen ASR API
**When**: The result is saved to `2_qwen_asr.json`
**Then**: File contains valid JSON with Qwen ASR response structure including `status_code` and `output` fields

#### Scenario: Invalid Output Path
**Given**: Output directory does not have write permissions
**When**: The system attempts to save `2_qwen_asr.json`
**Then**:
- It prints error: `✗ StudentName: Error - Permission denied`
- Processing continues to next student
- Skipped count is incremented

---

### Requirement: Progress Reporting

The system SHALL provide clear, structured progress reporting for batch operations, indicating the status of each student and a final summary.

#### Scenario: Processing Progress
**Given**: Batch processing of 3 students
**When**: Processing starts and progresses
**Then**: Each student processing prints status on own line:
- Success: `  ✓ Student1: Saved to 2_qwen_asr.json`
- Skipped: `  ✓ Student2: Already processed (skipping)`
- Error: `  ✗ Student3: Error - [error message]`

#### Scenario: Batch Summary
**Given**: Batch processing completes
**When**: All students are processed
**Then**: Final summary is printed with format:
```
============================================================
Batch processing complete!
Processed: N, Skipped: M
============================================================
```

---

### Requirement: Error Handling and Exit Codes

The system SHALL handle errors gracefully, provide informative error messages, and return appropriate exit codes (0 for success, 1 for fatal errors).

#### Scenario: API Key Missing
**Given**: User runs script without DASHSCOPE_API_KEY environment variable
**When**: Script executes
**Then**:
- It prints: `❌ Error: Please set DASHSCOPE_API_KEY environment variable`
- Exit code: 1

#### Scenario: Invalid Dataset Name
**Given**: User runs `python3 scripts/qwen_asr.py --dataset InvalidName`
**When**: Script executes
**Then**:
- It prints error message indicating dataset not found
- Exit code: 1

#### Scenario: Student Directory Not Found
**Given**: User runs `python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student NonExistent`
**When**: Script executes
**Then**:
- It prints: `Error: Student directory not found: homework_submission/Zoe51530/9.8/NonExistent/`
- Exit code: 1

#### Scenario: Successful Partial Processing
**Given**: Batch processing with some successes, some failures
**When**: Processing completes
**Then**:
- Exit code: 0 (partial success is acceptable)

---

### Requirement: CLI Help and Documentation

The script SHALL provide help information and usage examples through the `--help` argument.

#### Scenario: Help Display
**Given**: User runs `python3 scripts/qwen_asr.py --help`
**When**: Script executes
**Then**:
- It prints usage information including:
  - Script purpose: "Qwen ASR Batch Transcription Tool"
  - Available arguments: `--dataset`, `--student`, `--api-key`
  - Usage examples demonstrating all common use cases
- Exit code: 0

#### Scenario: Help Example for Dataset Processing
**Given**: User reads help output
**When**: Reviewing examples section
**Then**: Examples include:
```
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8
```
To demonstrate processing all students in a specific dataset

#### Scenario: Help Example for Single Student
**Given**: User reads help output
**When**: Reviewing examples section
**Then**: Examples include:
```
python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Oscar
```
To demonstrate processing a specific student

---

## MODIFIED Requirements

### Requirement: Backward Compatibility

Existing functionality SHALL remain intact and callable; there SHALL be no breaking changes to public API or default behavior.

#### Scenario: Direct Function Import
**Given**: External script imports `process_all_students` from `qwen_asr.py`
**When**: Function is called directly
**Then**:
- Function behavior is unchanged
- Still processes all datasets and students
- Still uses `2_qwen_asr.json` output naming
- No errors or warnings about deprecated usage

#### Scenario: Script Default Behavior
**Given**: Script is run with no arguments: `python3 scripts/qwen_asr.py`
**When**: Execution proceeds
**Then**:
- It runs `process_all_students()` internally (default behavior)
- Behavior is identical to current/previous version
- No CLI argument errors are raised
- Processes all datasets as before

---

## Testing Scenarios

### Unit Test Coverage
1. Dataset name parsing: Valid and invalid inputs
2. Student directory discovery: Empty and populated directories
3. Audio file detection: Priority order and fallback logic
4. Deduplication: Existing file detection and skip behavior
5. Exit code handling: Correct codes for success/error

### Integration Test Coverage
1. Full dataset processing: All students in one dataset
2. Single student processing: One specific student
3. Skip existing files: Mixed new and completed students
4. Error recovery: Handle API errors and continue
5. CLI integration: Argument parsing and routing

### Manual Test Coverage
1. Real API calls with production datasets
2. All CLI flag combinations
3. Error scenarios (missing files, API failures)
4. Performance and API quota impact

---

## Implementation Guidelines

### Technical Constraints
- Use `argparse` module for CLI argument parsing
- Use `pathlib.Path` for filesystem operations
- Support Python 3.12.12 compatibility
- Maintain Chinese comments for consistency

### Directory Structure
```
homework_submission/
└── <COURSE_CODE>/
    └── <DATE>/
        └── <STUDENT_NAME>/
            ├── 1_input_audio.mp3 (input)
            ├── 2_qwen_asr.json (output)
            └── other files
```

---

## Success Metrics

- ✅ CLI accepts and correctly parses `--dataset` and `--student` arguments
- ✅ Batch processing skips files where `2_qwen_asr.json` exists
- ✅ Output files are saved with correct naming and valid JSON format
- ✅ Progress reporting is clear and informative
- ✅ No breaking changes to existing code
- ✅ Exit codes are correct (0 for success, 1 for fatal errors)
- ✅ Error messages guide users to resolution
- ✅ Help command displays complete usage information
