# Change: Enhance Qwen ASR Batch Processing

**Change ID**: `enhance-qwen-asr-batch-processing`

**Status**: Draft Proposal

**Last Updated**: 2025-10-21

---

## Summary

Add command-line interface to `scripts/qwen_asr.py` to enable flexible batch transcription across homework datasets with idempotent output (automatic skipping of already-processed files).

### What's New

- **CLI Arguments**: `--dataset` and `--student` flags for selective processing
- **Batch Processing**: Process entire datasets or individual students
- **Deduplication**: Automatic skipping of files where `2_qwen_asr.json` already exists
- **Clear Reporting**: Progress indicators and summary statistics
- **Backward Compatible**: No breaking changes to existing functionality

### Use Cases

1. **Quick Start**: Process one student
   ```bash
   python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Oscar
   ```

2. **Batch Dataset**: Process entire class
   ```bash
   python3 scripts/qwen_asr.py --dataset Zoe51530-9.8
   ```

3. **Full Processing**: Process all datasets
   ```bash
   python3 scripts/qwen_asr.py
   ```

---

## Files in This Change

| File | Purpose |
|------|---------|
| `proposal.md` | High-level proposal and justification |
| `design.md` | Technical architecture and implementation details |
| `specs/qwen-asr-batch-transcription/spec.md` | Detailed requirements and scenarios |
| `tasks.md` | Implementation tasks and timeline |
| `README.md` | This file - overview and navigation |

---

## Key Capabilities

### 1. CLI Argument Interface
- Accept `--dataset` (optional) to specify dataset
- Accept `--student` (optional) to specify individual student
- Support `--api-key` to override DASHSCOPE_API_KEY
- Display help with `--help`

### 2. Dataset Discovery
- Auto-discover available datasets from `homework_submission/` directory
- Map dataset names (e.g., `Zoe51530-9.8`) to filesystem paths
- List students within each dataset

### 3. Audio File Detection
- Priority-based discovery of student audio files
- Support multiple formats: .mp3, .mp4, .wav, .m4a, .flac, .ogg
- Fallback to various naming conventions

### 4. Idempotent Processing
- Check if `2_qwen_asr.json` already exists
- Skip transcription if file is present
- Enable safe re-runs without duplicate API calls

### 5. Progress Reporting
- Clear per-student status (✓ success, ✗ error, ⊘ skipped)
- Summary of processed and skipped counts
- Error messages with actionable guidance

---

## Timeline

- **Phase 1** (CLI Infrastructure): 4-6 hours
- **Phase 2** (Processing Functions): 4-6 hours
- **Phase 3** (Testing): 6-9 hours
- **Phase 4** (Documentation): 1 hour
- **Total**: 15-22 hours

---

## Implementation Status

| Task | Status | Effort |
|------|--------|--------|
| ArgumentParser | Pending | 1-2h |
| Dataset name parsing | Pending | 30m |
| Dataset discovery | Pending | 1-2h |
| Audio file discovery | Pending | 1h |
| Deduplication check | Pending | 15m |
| Refactor main() | Pending | 1-2h |
| process_dataset() | Pending | 1-2h |
| process_student() | Pending | 1h |
| Unit tests | Pending | 2-3h |
| Integration tests | Pending | 3-4h |
| Manual testing | Pending | 1-2h |
| Documentation | Pending | 1h |

---

## Architecture Highlights

### Before
```
scripts/qwen_asr.py
├── QwenASRProvider (class)
└── process_all_students()
    └── main() [no CLI]
```

### After
```
scripts/qwen_asr.py
├── QwenASRProvider (class) [unchanged]
├── Helper functions [new]
│   ├── parse_dataset_name()
│   ├── find_datasets()
│   ├── find_students_in_dataset()
│   ├── find_audio_file()
│   └── should_process()
├── process_all_students() [unchanged]
├── process_dataset() [new]
├── process_student() [new]
└── main() [enhanced with CLI]
```

---

## Data Flow Example

**Command**: `python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Oscar`

```
User input
    ↓
main() parses args
    ↓
process_student("Zoe51530-9.8", "Oscar")
    ↓
Resolve path: homework_submission/Zoe51530/9.8/Oscar/
    ↓
Find audio file (priority order)
    ↓
Check: 2_qwen_asr.json exists? → Skip or Process
    ↓
QwenASRProvider.transcribe_and_save()
    ↓
Output: homework_submission/Zoe51530/9.8/Oscar/2_qwen_asr.json
```

---

## Success Metrics

✅ Checklist for this change:

- [ ] CLI accepts `--dataset` and `--student` arguments
- [ ] Batch processing skips existing `2_qwen_asr.json` files
- [ ] Output files have standardized naming: `2_qwen_asr.json`
- [ ] Progress reporting is clear and informative
- [ ] No breaking changes to existing API
- [ ] Exit codes correct (0 = success, 1 = error)
- [ ] Error messages guide users to resolution
- [ ] All tests passing (unit + integration)
- [ ] Backward compatibility confirmed

---

## Testing Strategy

### Unit Tests
- Dataset name parsing
- Student discovery
- Audio file detection
- Deduplication logic

### Integration Tests
- Full dataset processing
- Single student processing
- Error handling and recovery
- Backward compatibility

### Manual Testing
- Real API calls with production data
- All CLI flag combinations
- Error scenarios
- Performance baseline

---

## Next Steps

1. **Review**: Get feedback on proposal.md and design.md
2. **Refine**: Adjust based on feedback
3. **Validate**: Run `openspec validate enhance-qwen-asr-batch-processing`
4. **Approve**: Once validation passes, create PR
5. **Implement**: Follow tasks in tasks.md
6. **Test**: Execute test plan
7. **Deploy**: Merge and document in CLAUDE.md

---

## Questions & Considerations

- Should we support `--overwrite` flag to force re-transcription?
- Should we implement `--batch-delay` to respect API rate limits?
- Should we support filtering by student name pattern (regex)?
- Should we add `--progress-file` for resumable processing?

---

## Backward Compatibility

✅ **Fully backward compatible**

- Existing `QwenASRProvider` class unchanged
- Existing `process_all_students()` function unchanged
- Default behavior (no CLI args) runs `process_all_students()`
- No breaking changes to public API
- Existing code can still import and use the module

---

## References

- **Specification**: `specs/qwen-asr-batch-transcription/spec.md`
- **Design**: `design.md`
- **Tasks**: `tasks.md`
- **Related Code**: `scripts/qwen_asr.py`
- **Example Data**: `homework_submission/Zoe51530/9.8/`
