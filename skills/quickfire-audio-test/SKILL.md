---
name: quickfire-audio-test
description: Run audio-based annotation tests for Quickfire English pronunciation evaluation system. This skill should be used when the user needs to (1) Test audio input with Gemini models, (2) Run batch or sync annotation tests on student recordings, (3) Validate prompt changes with real audio, (4) Compare ASR-based vs audio-based evaluation approaches, or (5) Debug annotation pipeline with specific students.
---

# Quickfire Audio Testing

Run audio-based annotation tests for the Quickfire English pronunciation evaluation system. This skill provides workflows for both synchronous (fast iteration) and batch (cost-effective) testing modes.

## When to Use This Skill

Use this skill when:
- Testing audio input with Gemini models (gemini-3-pro-preview)
- Running annotation tests on student recordings
- Validating prompt changes with real audio files
- Comparing different evaluation approaches (ASR text vs direct audio)
- Debugging annotation pipeline failures
- Processing entire class batches with cost optimization

## Testing Modes

### Mode 1: Synchronous Audio Test (Fast Iteration)

**When to use**: Quick validation of prompt changes, debugging single students, immediate feedback needed

**Workflow**:
```bash
# Test single student with audio input
uv run python scripts/main.py \
  --archive-batch <batch-id> \
  --student <student-name> \
  --annotator gemini-audio

# Preview without API calls
uv run python scripts/main.py \
  --archive-batch <batch-id> \
  --student <student-name> \
  --annotator gemini-audio \
  --dry-run

# Force re-run with fresh annotation
uv run python scripts/main.py \
  --archive-batch <batch-id> \
  --student <student-name> \
  --annotator gemini-audio \
  --force
```

**Output location**:
```
archive/<batch-id>/<student>/runs/gemini-3-pro-preview/<run-id>/
├── 4_llm_annotation.json    # Grading results (A/B/C + annotations)
├── prompt_log.txt            # Full prompt for debugging
└── run_manifest.json         # Input file hashes + git commit
```

**Characteristics**:
- Real-time API calls (2-3 minutes per student)
- Immediate results in student's run directory
- Suitable for prompt iteration and debugging
- Higher cost (standard API pricing)

### Mode 2: Batch Audio Test (Cost Optimization)

**When to use**: Processing entire classes, cost-sensitive scenarios, overnight batch jobs

**One-step workflow** (recommended):
```bash
# Process entire batch with Batch API (50% cost savings)
uv run python scripts/main.py \
  --archive-batch <batch-id> \
  --batch-audio

# Process specific students only
uv run python scripts/main.py \
  --archive-batch <batch-id> \
  --student <student1>,<student2> \
  --batch-audio
```

**Advanced workflow** (manual control):
```bash
# Step 1: Submit batch job
uv run python scripts/gemini_batch_audio.py submit \
  --archive-batch <batch-id>

# Step 2: Fetch results when ready (use manifest path from step 1)
uv run python scripts/gemini_batch_audio.py fetch \
  --manifest archive/<batch-id>/_batch_runs/<run-id>.audio/batch_manifest.json
```

**Output location**:
```
archive/<batch-id>/_batch_runs/<run-id>.audio/
├── batch_manifest.json       # Job metadata (tokens, timing)
├── batch_report.json         # Class summary (grade distribution)
├── batch_input.jsonl         # API request payload
├── batch_output.jsonl        # Raw API responses
└── students/                 # Per-student detailed reports
    ├── <student1>.json
    └── <student2>.json

# Individual student results also saved to:
archive/<batch-id>/<student>/runs/gemini-3-pro-preview.audio/<run-id>/
└── 4_llm_annotation.json
```

**Characteristics**:
- 50% cost savings vs synchronous mode
- Processes multiple students in parallel
- Longer wait time (10-20 minutes for batch processing)
- Comprehensive batch-level reporting

## Common Workflows

### Validate Prompt Changes

After editing `prompts/annotation/user_with_audio.md`:

```bash
# Quick test with 1-2 students
uv run python scripts/main.py \
  --archive-batch <test-batch> \
  --student <student-name> \
  --annotator gemini-audio

# Review prompt used
cat "archive/<batch-id>/<student>/runs/gemini-3-pro-preview/*/prompt_log.txt"

# Check annotation results
cat "archive/<batch-id>/<student>/runs/gemini-3-pro-preview/*/4_llm_annotation.json"
```

### Debug Annotation Failures

```bash
# List available batches
ls archive/

# List students in batch
ls archive/<batch-id>/

# Check student's audio file exists
ls archive/<batch-id>/<student>/1_input_audio.mp3

# Run with verbose output
uv run python scripts/main.py \
  --archive-batch <batch-id> \
  --student <student-name> \
  --annotator gemini-audio

# Inspect generated prompt
cat "archive/<batch-id>/<student>/runs/gemini-3-pro-preview/*/prompt_log.txt"
```

### Process Entire Class

```bash
# Preview student list
ls archive/<batch-id>/

# Batch process all students (recommended)
uv run python scripts/main.py \
  --archive-batch <batch-id> \
  --batch-audio

# Monitor results
cat "archive/<batch-id>/_batch_runs/*/.audio/batch_report.json"
```

### Compare Test Runs

```bash
# List all runs for a student
ls -lt archive/<batch-id>/<student>/runs/gemini-3-pro-preview/

# Compare annotation results
diff \
  archive/<batch-id>/<student>/runs/gemini-3-pro-preview/<run-id-1>/4_llm_annotation.json \
  archive/<batch-id>/<student>/runs/gemini-3-pro-preview/<run-id-2>/4_llm_annotation.json

# Check which prompt version was used
grep "Prompt Version" \
  archive/<batch-id>/<student>/runs/gemini-3-pro-preview/*/prompt_log.txt
```

## Important Configuration

### Required Model

Per project rules in `CLAUDE.md`:
- **MUST use**: `gemini-3-pro-preview` (default for audio mode)
- Reason: Best audio understanding and multi-language annotation performance
- Can detect audio anomalies (e.g., NO_TEACHER_AUDIO)

### Environment Variables

Ensure these are configured in `.env`:
```bash
GEMINI_API_KEY=AIzaSy...      # Google Gemini API
DASHSCOPE_API_KEY=sk-xxx      # Alibaba Qwen ASR (for preprocessing)
```

Verify configuration:
```bash
cat .env | grep GEMINI_API_KEY
cat .env | grep DASHSCOPE_API_KEY
```

### Pipeline Dependencies

Audio annotation requires prior ASR processing:
1. **ASR stage** (`2_qwen_asr.json`) - Auto-runs before annotation
2. **Audio file** (`1_input_audio.mp3`) - Must exist in student directory
3. **Question bank** - Referenced in `archive/<batch-id>/metadata.json`

To skip ASR and test annotation only:
```bash
# Assumes 2_qwen_asr.json already exists
uv run python scripts/main.py \
  --archive-batch <batch-id> \
  --student <student-name> \
  --only cards \
  --annotator gemini-audio
```

## Output Format

### Annotation Result Structure

```json
{
  "student_name": "Qihang",
  "final_grade_suggestion": "A",
  "mistake_count": { "errors": 0 },
  "annotations": [
    {
      "card_index": 1,
      "card_timestamp": "00:01",
      "question": "celebrate",
      "expected_answer": "庆祝",
      "related_student_utterance": {
        "detected_text": "庆祝",
        "issue_type": null
      }
    }
  ],
  "_metadata": {
    "model": "gemini-3-pro-preview",
    "mode": "sync",
    "timestamp": "2026-02-03T10:30:00",
    "audio_duration_seconds": 180.5,
    "token_usage": {
      "prompt_tokens": 12000,
      "candidates_tokens": 3000,
      "total_tokens": 15000
    }
  }
}
```

### Grading Rules

- **Grade A**: 0 errors
- **Grade B**: 1-2 errors
- **Grade C**: 3+ errors

### Error Types

- `null` - Correct answer
- `NO_ANSWER` - Student did not respond
- `MEANING_ERROR` - Incorrect translation/meaning

## Troubleshooting

### "No audio file found"

```bash
# Check expected file location
ls archive/<batch-id>/<student>/1_input_audio.mp3

# Verify metadata.json exists
cat archive/<batch-id>/metadata.json
```

### "ASR file not found"

```bash
# Run ASR stage first
uv run python scripts/main.py \
  --archive-batch <batch-id> \
  --student <student-name> \
  --only qwen_asr

# Then run annotation
uv run python scripts/main.py \
  --archive-batch <batch-id> \
  --student <student-name> \
  --only cards \
  --annotator gemini-audio
```

### Batch job stuck/failed

```bash
# Check job status with manifest
cat archive/<batch-id>/_batch_runs/<run-id>.audio/batch_manifest.json

# Re-fetch if needed
uv run python scripts/gemini_batch_audio.py fetch \
  --manifest archive/<batch-id>/_batch_runs/<run-id>.audio/batch_manifest.json
```

### Network/proxy issues

Ensure proxy is configured (default: `socks5://127.0.0.1:7890`):
```bash
# Check proxy environment
echo $HTTPS_PROXY

# Or set proxy in custom function
set_proxy  # User's custom function per CLAUDE.md
```

## Performance Benchmarks

| Metric | Synchronous Mode | Batch Mode |
|--------|------------------|------------|
| Cost | Standard pricing | 50% savings |
| Speed | 2-3 min/student | 10-20 min total (parallel) |
| Use case | Debugging, iteration | Production, bulk processing |
| Output | Individual runs | Batch + individual runs |

## References

- Main pipeline: `scripts/main.py` - DAG orchestration
- Sync annotator: `scripts/annotators/gemini_audio.py` - Audio annotation
- Batch handler: `scripts/gemini_batch_audio.py` - Batch API integration
- Project rules: `CLAUDE.md` - Model requirements and testing modes
- README: `README.md` - System architecture overview
