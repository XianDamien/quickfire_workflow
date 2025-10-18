# Specification: Evaluation Workflow (evaluation-workflow) - Delta

## Overview

This delta modifies the evaluation workflow capability to support multiple ASR engines for transcription.

## MODIFIED Requirements

### Requirement: Workflow with Multi-Engine ASR Support

The workflow execution SHALL accept a parameter `--asr-engine` to select between different ASR engines (Qwen or FunASR), defaulting to Qwen for backward compatibility.

#### Previous Behavior

The workflow always used Qwen multi-modal ASR for transcription. Users could only run:

```bash
python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/qb.csv
```

#### New Behavior

Users can now specify the ASR engine and provide appropriate parameters:

```bash
# Qwen ASR (default, backward compatible)
python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/qb.csv

# FunASR (new option)
python3 workflow.py --audio-path ./audio/sample.mp3 --qb-path ./data/qb.csv \
  --asr-engine funasr --oss-region cn-hangzhou --oss-bucket my-bucket
```

#### Scenario: Multi-Engine Workflow Execution

**Given:**
- Local audio file and question bank CSV
- User prefers FunASR for transcription
- OSS credentials available

**When:**
- User runs: `workflow.py --audio-path ... --qb-path ... --asr-engine funasr --oss-region ... --oss-bucket ...`

**Then:**
- Workflow:
  1. Uploads local audio to OSS
  2. Calls FunASR for transcription via OSS URL
  3. Normalizes FunASR output to standard format
  4. Loads question bank
  5. Executes pronunciation evaluation
  6. Outputs JSON report with same structure as Qwen path
- Result is functionally identical to Qwen ASR path (only transcription engine differs)

#### Scenario: Default Engine (Backward Compatible)

**Given:**
- Existing workflow usage without `--asr-engine` parameter

**When:**
- User runs: `workflow.py --audio-path ... --qb-path ...`

**Then:**
- Workflow defaults to Qwen ASR (existing behavior)
- No behavioral change from user perspective

### Requirement: Parameter Validation and Error Handling

The workflow SHALL validate parameters based on selected engine and MUST provide clear error messages when required parameters are missing.

#### Scenario: FunASR Mode Parameter Validation

**Given:**
- User specifies `--asr-engine funasr`

**When:**
- User omits `--oss-region` or `--oss-bucket`

**Then:**
- Workflow exits immediately with error message
- Message clearly states which parameters are missing
- Message provides example usage

#### Scenario: Invalid Engine Selection

**Given:**
- User specifies invalid `--asr-engine` value

**When:**
- Workflow is invoked with `--asr-engine invalid_engine`

**Then:**
- Workflow exits with error
- Error message lists valid options: {qwen, funasr}

## Data Flow Changes

### Qwen Path (Unchanged)

```
Local Audio → Qwen ASR → Standard Format → Evaluation → Report
```

### FunASR Path (New)

```
Local Audio → Upload to OSS → FunASR → Normalize → Evaluation → Report
```

### Combined View

```
                    ┌─────────┐
                    │Local    │
                    │Audio    │
                    └────┬────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
    Qwen Path                         FunASR Path
        │                                 │
        ▼                                 ▼
   Qwen ASR                          OSS Upload
        │                                 │
        └────────────┬────────────────────┘
                     │
                     ▼
              Standard Format
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
    QB Load              Evaluation Engine
        │                        │
        └────────────┬───────────┘
                     │
                     ▼
                JSON Report
```

## Environment and Configuration

### New Environment Variables (optional, for default values)

```bash
# Can be set as defaults, but CLI parameters take precedence
OSS_REGION=cn-hangzhou
OSS_BUCKET=my-bucket
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
```

### New CLI Parameters

| Parameter | Mode | Type | Required | Default | Description |
|-----------|------|------|----------|---------|-------------|
| `--asr-engine` | global | enum {qwen\|funasr} | No | qwen | ASR engine selection |
| `--oss-region` | FunASR | string | Yes (if FunASR) | - | OSS region code |
| `--oss-bucket` | FunASR | string | Yes (if FunASR) | - | OSS bucket name |
| `--oss-endpoint` | FunASR | string | No | auto | OSS endpoint URL |
| `--keep-oss-file` | FunASR | flag | No | false | Keep file in OSS after transcription |

## Output Format

The final JSON report structure **remains unchanged** regardless of ASR engine:

```json
{
  "final_grade_suggestion": "A/B/C",
  "mistake_count": {
    "hard_errors": 0,
    "soft_errors": 0
  },
  "annotations": [...]
}
```

**Note:** Transcription engine choice does not affect evaluation results or output format.

## Backward Compatibility

✅ **100% backward compatible:**
- Old command format still works: `workflow.py --audio-path ... --qb-path ...`
- Default behavior is unchanged (Qwen ASR)
- All new parameters are optional
- Existing scripts and workflows need zero modification

## Observability

### New Logging Points

- Engine selection: "[info] Using ASR engine: funasr"
- Upload progress: "[info] Uploading audio to OSS: 5.2 MB"
- Upload result: "[info] OSS URL: oss://... (status: 200)"
- Polling progress: "[info] Transcription task polling (attempt 3/10)"
- Transcription result: "[info] Transcription completed in 8.5s, 5 speakers detected"

## Related Capabilities

- **audio-transcription**: Defines the new FunASR transcription capability
- **ai-result-output**: Unchanged; evaluation results format is constant
