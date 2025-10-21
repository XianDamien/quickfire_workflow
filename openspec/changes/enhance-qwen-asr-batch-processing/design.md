# Design: Enhance Qwen ASR Batch Processing

**Change ID**: `enhance-qwen-asr-batch-processing`

## Architecture Overview

### Current State
```
scripts/qwen_asr.py
├── QwenASRProvider (class)
│   ├── transcribe_audio()
│   └── transcribe_and_save()
└── process_all_students() [existing batch function]
    └── main() [no CLI, direct function call]
```

### Proposed State
```
scripts/qwen_asr.py
├── QwenASRProvider (class) [UNCHANGED]
│   ├── transcribe_audio()
│   └── transcribe_and_save()
├── DatasetDiscovery (new helper)
│   ├── find_datasets()
│   ├── find_students()
│   └── find_audio_files()
├── process_all_students() [UNCHANGED - kept for backward compatibility]
├── process_dataset() [NEW - filtered processing]
├── process_student() [NEW - single student processing]
└── main() [ENHANCED - CLI argument parsing]
    └── ArgumentParser
        ├── --dataset (optional)
        ├── --student (optional)
        └── --api-key (optional)
```

## Data Flow

### Scenario 1: Full Batch Processing
```
User: python3 scripts/qwen_asr.py
      ↓
main() → parse args (no --dataset, no --student)
      ↓
process_all_students() [existing]
      ↓
Iterate: homework_submission/<DATASET>/<STUDENT>/
      ↓
For each: Check for 2_qwen_asr.json → Skip or Process
      ↓
Output: multiple 2_qwen_asr.json files
```

### Scenario 2: Dataset Filtering
```
User: python3 scripts/qwen_asr.py --dataset Zoe51530-9.8
      ↓
main() → parse args
      ↓
process_dataset("Zoe51530-9.8")
      ↓
Discover: homework_submission/Zoe51530/9.8/<STUDENT>/
      ↓
For each student: Check for 2_qwen_asr.json → Skip or Process
      ↓
Output: 2_qwen_asr.json in each student's folder
```

### Scenario 3: Single Student
```
User: python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Oscar
      ↓
main() → parse args
      ↓
process_student("Zoe51530-9.8", "Oscar")
      ↓
Check: homework_submission/Zoe51530/9.8/Oscar/
      ↓
Find audio → Check for 2_qwen_asr.json
      ↓
Process if not exists
      ↓
Output: homework_submission/Zoe51530/9.8/Oscar/2_qwen_asr.json
```

## Implementation Details

### 1. CLI Argument Parser

```python
import argparse

parser = argparse.ArgumentParser(
    description='Qwen ASR Batch Transcription Tool',
    epilog="""
Examples:
  python3 qwen_asr.py                                    # All datasets, all students
  python3 qwen_asr.py --dataset Zoe51530-9.8            # Specific dataset, all students
  python3 qwen_asr.py --dataset Zoe51530-9.8 --student Oscar  # Specific student
    """
)

parser.add_argument(
    '--dataset',
    type=str,
    help='Dataset name (e.g., Zoe51530-9.8). Format: CourseName-Date'
)

parser.add_argument(
    '--student',
    type=str,
    help='Student name to process (requires --dataset)'
)

parser.add_argument(
    '--api-key',
    type=str,
    help='DashScope API key (optional, defaults to DASHSCOPE_API_KEY env var)'
)

args = parser.parse_args()
```

### 2. Dataset Discovery

Map CLI flags to filesystem paths:

```
User input: --dataset Zoe51530-9.8
            ↓
Parse: CourseName="Zoe51530", Date="9.8"
            ↓
Search: homework_submission/Zoe51530/9.8/
            ↓
Discover: [Oscar, Yiyi, Phoebe, Kevin, ...]
```

**Dataset name format**: `<COURSE_CODE>-<DATE>`
- Example: `Zoe51530-9.8` → `homework_submission/Zoe51530/9.8/`
- Example: `Zoe41900-9.8` → `homework_submission/Zoe41900/9.8/`

### 3. Student Audio Discovery

For each student directory, detect audio files:

```
Student directory: homework_submission/Zoe51530/9.8/Oscar/

Search for: *.mp3, *.mp4, *.wav, *.m4a, *.flac, *.ogg

Priority order (first found is used):
1. 1_input_audio.* (standard naming)
2. <StudentName>.mp3
3. Any audio file in directory

Skip: Reference audio in references/ subdirectory
```

### 4. Deduplication Logic

Before transcription, check for output file existence:

```python
output_file = student_dir / "2_qwen_asr.json"

if output_file.exists():
    print(f"  ✓ {student_name}: Already processed (skipping)")
    return SKIPPED
else:
    # Perform transcription
    transcribe_and_save(...)
    return PROCESSED
```

### 5. Output Structure

All outputs follow naming convention `2_qwen_asr.json`:

```
homework_submission/Zoe51530/9.8/
├── Oscar/
│   ├── 1_input_audio.mp3 (input)
│   ├── 2_qwen_asr.json (output - NEW)
│   └── ...
├── Yiyi/
│   ├── 1_input_audio.mp3
│   ├── 2_qwen_asr.json
│   └── ...
└── ...
```

JSON schema (inherited from `QwenASRProvider.transcribe_and_save()`):

```json
{
  "status_code": 200,
  "output": {
    "choices": [
      {
        "message": {
          "content": "audio_transcription_text"
        }
      }
    ]
  },
  ...
}
```

## Error Handling

| Error | Handling |
|-------|----------|
| Dataset not found | Print error message, exit with code 1 |
| Student not found | Print error message, exit with code 1 |
| No audio files in student dir | Print warning, skip student |
| Transcription fails (API error) | Print error, continue to next student |
| API key missing | Print error, exit with code 1 |

## Backward Compatibility

1. **Existing `process_all_students()` function**:
   - Preserved unchanged
   - Can still be called directly by other scripts
   - Default behavior when no arguments provided

2. **Existing `QwenASRProvider` class**:
   - No changes to public API
   - No breaking changes

3. **Existing `main()` function**:
   - Wrapped with CLI argument parser
   - Falls back to `process_all_students()` if called without args
   - Maintains same exit codes

## Sequence Diagram

```
User
  │
  ├─→ python3 scripts/qwen_asr.py --dataset Zoe51530-9.8 --student Oscar
  │
  ├─→ main()
  │   ├─→ Parse arguments
  │   │   └─→ args.dataset = "Zoe51530-9.8"
  │   │   └─→ args.student = "Oscar"
  │   │
  │   ├─→ Validate --student requires --dataset
  │   │
  │   └─→ process_student("Zoe51530-9.8", "Oscar")
  │       ├─→ Parse dataset: CourseName="Zoe51530", Date="9.8"
  │       ├─→ Resolve path: homework_submission/Zoe51530/9.8/Oscar/
  │       ├─→ Find audio file in directory
  │       ├─→ Check if 2_qwen_asr.json exists
  │       │   └─→ If exists: Skip (print ✓)
  │       │   └─→ If not: Process
  │       ├─→ provider.transcribe_and_save(
  │       │       audio_path, student_dir,
  │       │       output_filename="2_qwen_asr.json"
  │       │   )
  │       └─→ Return status (PROCESSED or SKIPPED)
  │
  └─→ Print summary
      ├─→ Total processed: N
      ├─→ Total skipped: M
      └─→ Exit with code 0
```

## Performance Considerations

1. **API quota**: Batch processing may hit DashScope rate limits
   - Implement optional `--batch-delay` parameter for future enhancement
   - Current: No delays, rely on API rate limiting

2. **Memory**: Store only one audio result at a time
   - Stream-friendly design

3. **Filesystem**: Use `Path` instead of string concatenation
   - Portable across OS

## Testing Strategy

### Unit Tests
```python
def test_parse_dataset_name():
    """Test parsing Zoe51530-9.8 → Zoe51530/9.8"""

def test_find_students_in_dataset():
    """Test discovering student directories"""

def test_find_audio_file_in_student_dir():
    """Test audio file detection and priority"""

def test_deduplication_skip_existing():
    """Test that existing 2_qwen_asr.json is skipped"""
```

### Integration Tests
```python
def test_process_dataset_all_students():
    """End-to-end: Process entire dataset"""

def test_process_single_student():
    """End-to-end: Process single student"""

def test_cli_argument_parsing():
    """Test various CLI argument combinations"""
```

## Migration Notes

- No database migrations needed
- No configuration file changes
- Existing batch results can remain unchanged
- CLI is purely additive enhancement

## Future Enhancements

1. **`--batch-delay`**: Add delay between API calls
2. **`--dry-run`**: Simulate processing without API calls
3. **`--overwrite`**: Force re-transcription of existing files
4. **`--progress-file`**: Save progress to JSON for resumable processing
5. **`--filter-students`**: Regex filter for student names
6. **`--output-format`**: Support different output formats (CSV, etc.)
