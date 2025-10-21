# Implementation Tasks: Enhance Qwen ASR Batch Processing

**Change ID**: `enhance-qwen-asr-batch-processing`

**Status**: Draft

---

## Phase 1: Core CLI Infrastructure (3-4 tasks)

### Task 1: Add ArgumentParser to scripts/qwen_asr.py
**Objective**: Implement command-line argument parsing for `--dataset`, `--student`, and `--api-key`

**Details**:
- Import `argparse` module
- Create `ArgumentParser` with description and epilog
- Add `--dataset` argument (optional, type=str)
- Add `--student` argument (optional, type=str)
- Add `--api-key` argument (optional, type=str)
- Validate: `--student` requires `--dataset` (mutual dependency)
- Parse arguments in `main()` function

**Acceptance Criteria**:
- ✓ `python3 scripts/qwen_asr.py --help` displays usage
- ✓ Arguments are correctly parsed
- ✓ Invalid argument combinations show error and exit(1)

**Estimated Effort**: 1-2 hours

**Dependencies**: None

---

### Task 2: Implement Dataset Name Parsing
**Objective**: Convert dataset names (e.g., `Zoe51530-9.8`) to filesystem paths

**Details**:
- Create `parse_dataset_name(dataset_name: str) -> tuple[str, str]` function
- Split by `-` to extract course code and date: `Zoe51530-9.8` → (`Zoe51530`, `9.8`)
- Validate format (raise error if invalid)
- Return tuple: `(course_code, date)`

**Acceptance Criteria**:
- ✓ `parse_dataset_name("Zoe51530-9.8")` returns `("Zoe51530", "9.8")`
- ✓ `parse_dataset_name("invalid")` raises ValueError with clear message
- ✓ Handles edge cases (extra hyphens, missing parts)

**Estimated Effort**: 30 minutes

**Dependencies**: Task 1 (needs CLI arguments)

---

### Task 3: Implement Dataset Discovery
**Objective**: Discover available datasets and student directories

**Details**:
- Create `find_datasets() -> List[str]` function
  - Scan `homework_submission/` directory
  - Return list of discovered datasets (e.g., ["Zoe51530", "Zoe41900", ...])
- Create `find_students_in_dataset(course_code: str, date: str) -> List[str]` function
  - Given course code and date, list student directories
  - Return list of student names
- Create `resolve_dataset_path(dataset_name: str) -> Path` function
  - Use `parse_dataset_name()` to extract parts
  - Resolve to `homework_submission/<COURSE>/<DATE>/` path
  - Return Path object

**Acceptance Criteria**:
- ✓ `find_datasets()` returns list of available datasets
- ✓ `find_students_in_dataset("Zoe51530", "9.8")` returns student list
- ✓ `resolve_dataset_path("Zoe51530-9.8")` returns correct Path object
- ✓ Non-existent datasets raise clear error

**Estimated Effort**: 1-2 hours

**Dependencies**: Task 2

---

### Task 4: Implement Audio File Discovery
**Objective**: Auto-detect student audio files with priority-based fallback

**Details**:
- Create `find_audio_file(student_dir: Path) -> Path | None` function
- Implement priority order:
  1. `1_input_audio.*` (any format)
  2. `<StudentName>.*` (matches directory name)
  3. First audio file by filesystem order
  4. Return None if not found
- Supported formats: .mp3, .mp4, .wav, .m4a, .flac, .ogg
- Ignore files in `references/` subdirectory

**Acceptance Criteria**:
- ✓ Finds `1_input_audio.mp3` when present
- ✓ Falls back to `StudentName.mp3` when standard naming missing
- ✓ Handles mixed audio formats
- ✓ Returns None when no audio found
- ✓ Ignores reference audio files

**Estimated Effort**: 1 hour

**Dependencies**: Task 3

---

## Phase 2: Processing Functions (2-3 tasks)

### Task 5: Implement Deduplication Check
**Objective**: Check if `2_qwen_asr.json` already exists

**Details**:
- Create `should_process(student_dir: Path) -> bool` function
- Check if `student_dir / "2_qwen_asr.json"` exists
- Return True if should process (file doesn't exist)
- Return False if should skip (file exists)
- No file I/O side effects

**Acceptance Criteria**:
- ✓ Returns True when output file doesn't exist
- ✓ Returns False when output file exists
- ✓ Handles Path objects correctly

**Estimated Effort**: 15 minutes

**Dependencies**: Task 3

---

### Task 6: Refactor main() for CLI Integration
**Objective**: Update main() to handle CLI arguments and dispatch to processing functions

**Details**:
- Parse CLI arguments: dataset, student, api-key
- Validate arguments and environment variables
- Route to appropriate processing function:
  - No args: `process_all_students()` (backward compat)
  - `--dataset` only: `process_dataset(dataset_name)`
  - `--dataset` + `--student`: `process_student(dataset_name, student_name)`
- Catch exceptions and print errors with exit code 1
- Return exit code 0 on success

**Acceptance Criteria**:
- ✓ `python3 scripts/qwen_asr.py` runs `process_all_students()`
- ✓ `python3 scripts/qwen_asr.py --dataset X` routes to `process_dataset(X)`
- ✓ `python3 scripts/qwen_asr.py --dataset X --student Y` routes to `process_student(X, Y)`
- ✓ Error messages are clear and informative
- ✓ Exit codes are correct (0/1)

**Estimated Effort**: 1-2 hours

**Dependencies**: Tasks 1-5

---

### Task 7: Create process_dataset() Function
**Objective**: Implement batch processing for entire dataset

**Details**:
- Create `process_dataset(dataset_name: str, api_key: Optional[str] = None) -> tuple[int, int]` function
- Parameters:
  - `dataset_name`: e.g., "Zoe51530-9.8"
  - `api_key`: Override DASHSCOPE_API_KEY (optional)
- Logic:
  1. Resolve dataset path
  2. Discover all students in dataset
  3. For each student:
     - Find audio file (skip if not found)
     - Check deduplication (skip if exists)
     - Process with `QwenASRProvider.transcribe_and_save()`
     - Print progress: ✓ or ✗
  4. Return (processed_count, skipped_count)

**Acceptance Criteria**:
- ✓ Processes all students in dataset
- ✓ Skips students with existing `2_qwen_asr.json`
- ✓ Handles missing audio files gracefully
- ✓ Handles API errors gracefully
- ✓ Returns accurate counts
- ✓ Progress output is clear

**Estimated Effort**: 1-2 hours

**Dependencies**: Tasks 3-5

---

### Task 8: Create process_student() Function
**Objective**: Implement processing for single student

**Details**:
- Create `process_student(dataset_name: str, student_name: str, api_key: Optional[str] = None) -> int` function
- Parameters:
  - `dataset_name`: e.g., "Zoe51530-9.8"
  - `student_name`: e.g., "Oscar"
  - `api_key`: Override DASHSCOPE_API_KEY (optional)
- Logic:
  1. Resolve dataset path
  2. Validate student directory exists
  3. Find audio file (error if not found)
  4. Check deduplication (skip if exists)
  5. Process with `QwenASRProvider.transcribe_and_save()`
  6. Print result
- Return: 0 on success, 1 on error

**Acceptance Criteria**:
- ✓ Processes single student correctly
- ✓ Returns error if student directory not found
- ✓ Returns error if no audio file found
- ✓ Skips if `2_qwen_asr.json` exists
- ✓ Saves output to correct location
- ✓ Exit code is correct

**Estimated Effort**: 1 hour

**Dependencies**: Tasks 3-5

---

## Phase 3: Testing & Validation (2-3 tasks)

### Task 9: Unit Tests for Dataset/Student Discovery
**Objective**: Create unit tests for helper functions

**Details**:
- Create `tests/test_qwen_asr_discovery.py` (or equivalent)
- Test `parse_dataset_name()`: valid/invalid inputs
- Test `find_datasets()`: dataset discovery
- Test `find_students_in_dataset()`: student listing
- Test `find_audio_file()`: priority order, fallbacks
- Test `should_process()`: deduplication logic

**Acceptance Criteria**:
- ✓ All unit tests pass
- ✓ >80% code coverage for discovery functions
- ✓ Tests cover edge cases (empty dirs, missing files, etc.)

**Estimated Effort**: 2-3 hours

**Dependencies**: Tasks 1-5

---

### Task 10: Integration Tests
**Objective**: Create end-to-end tests for processing workflows

**Details**:
- Create test fixtures: mock homework_submission directory with sample audio
- Test `process_dataset()`: full batch processing
- Test `process_student()`: single student processing
- Test deduplication: skip existing `2_qwen_asr.json`
- Test error handling: missing audio, API errors, etc.
- Test CLI integration: argument parsing and routing

**Acceptance Criteria**:
- ✓ All integration tests pass
- ✓ Tests verify correct output file creation
- ✓ Tests verify skip behavior for existing files
- ✓ Tests verify error handling
- ✓ No actual API calls (mock responses)

**Estimated Effort**: 3-4 hours

**Dependencies**: Tasks 1-8

---

### Task 11: Manual Testing & Validation
**Objective**: Test against real datasets with real API

**Details**:
1. Test with `--dataset Zoe51530-9.8`:
   - Process all students
   - Verify `2_qwen_asr.json` created in each directory
   - Check JSON format is valid

2. Test with `--dataset Zoe51530-9.8 --student Oscar`:
   - Process only Oscar
   - Verify output created
   - Verify idempotency (run again, should skip)

3. Test error scenarios:
   - Invalid dataset name
   - Non-existent student
   - Missing DASHSCOPE_API_KEY
   - Network/API errors

4. Verify backward compatibility:
   - Run `python3 scripts/qwen_asr.py` with no args
   - Should process all datasets as before

**Acceptance Criteria**:
- ✓ All real API tests pass
- ✓ Output files are valid JSON
- ✓ Idempotency works as expected
- ✓ Error messages are helpful
- ✓ Backward compatibility confirmed

**Estimated Effort**: 1-2 hours (excluding API wait times)

**Dependencies**: Tasks 1-8, deployment

---

## Phase 4: Documentation & Polish (1 task)

### Task 12: Update Documentation
**Objective**: Add CLI documentation and update inline comments

**Details**:
- Update `scripts/CLAUDE.md` with CLI usage examples
- Add inline code comments (Chinese) explaining CLI logic
- Create `scripts/QWEN_ASR_CLI_GUIDE.md` if needed
- Update `README.md` with new capability
- Document new functions with docstrings

**Acceptance Criteria**:
- ✓ Usage examples in CLAUDE.md
- ✓ All functions have docstrings
- ✓ CLI help text is clear and complete
- ✓ Error messages guide users to solutions

**Estimated Effort**: 1 hour

**Dependencies**: All previous tasks

---

## Dependency Graph

```
Task 1 (ArgumentParser)
    ↓
Task 2 (Dataset name parsing)
    ↓
Task 3 (Dataset discovery)
    ├→ Task 4 (Audio file discovery)
    ├→ Task 5 (Deduplication check)
    ├→ Task 6 (Refactor main) ← depends on all above
    ├→ Task 7 (process_dataset)
    └→ Task 8 (process_student)

Tasks 7-8
    ↓
Task 9 (Unit tests)
    ↓
Task 10 (Integration tests)
    ↓
Task 11 (Manual testing)
    ↓
Task 12 (Documentation)
```

---

## Timeline Estimate

| Phase | Tasks | Duration | Notes |
|-------|-------|----------|-------|
| Phase 1 | 1-4 | 4-6 hours | CLI infrastructure |
| Phase 2 | 5-8 | 4-6 hours | Processing functions |
| Phase 3 | 9-11 | 6-9 hours | Testing & validation |
| Phase 4 | 12 | 1 hour | Documentation |
| **Total** | | **15-22 hours** | Depends on testing scope |

---

## Verification Checklist

- [x] All CLI arguments parse correctly
- [x] Dataset discovery works for all formats
- [x] Audio file detection prioritizes correctly
- [x] Deduplication skips existing files
- [x] Processing functions handle errors gracefully
- [x] Output files are valid JSON in correct location
- [x] Progress reporting is clear and accurate
- [x] Exit codes are correct (0/1)
- [x] Backward compatibility maintained
- [ ] Unit tests pass (>80% coverage)
- [ ] Integration tests pass
- [ ] Manual testing with real API passes
- [ ] Documentation is complete and clear
- [x] No breaking changes to public API

---

## Rollback Procedure

If issues occur:
1. Revert changes to `scripts/qwen_asr.py`
2. Keep `scripts/qwen_asr.py` unchanged initially; add new functions without modifying `main()`
3. If major issues: restore from git commit before changes
4. `process_all_students()` remains functional as fallback

---

## Notes

- All tasks should maintain Python 3.12.12 compatibility
- Use `pathlib.Path` for cross-platform filesystem compatibility
- Chinese comments for consistency with existing codebase
- No new external dependencies required
- All tests should run without real API calls (use mocks)
- Consider future enhancement: `--batch-delay` for rate limiting
