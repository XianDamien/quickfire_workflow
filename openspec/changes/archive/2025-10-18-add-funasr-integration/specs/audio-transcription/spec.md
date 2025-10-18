# Specification: Audio Transcription (audio-transcription)

## Overview

Audio transcription capability defines the interface and behavior for converting audio files to text using different ASR (Automatic Speech Recognition) engines.

## ADDED Requirements

### Requirement: FunASR Engine Support

The system SHALL support FunASR (Alibaba DashScope official ASR service) as an alternative to Qwen multi-modal ASR for audio transcription.

#### Scenario: Basic FunASR Transcription

**Given:**
- A local audio file (MP3/WAV) located at `./audio/test.mp3`
- OSS bucket credentials configured via environment variables
- DashScope API key set in `DASHSCOPE_API_KEY`

**When:**
- User calls `transcribe_with_funasr()` with the OSS URL of uploaded audio

**Then:**
- The function submits an async transcription task to FunASR
- Polls the task status up to 10 times (max ~20 seconds)
- Returns transcription result in standard JSON format
- Result includes speaker identification (spk0, spk1) and timestamps in milliseconds

#### Scenario: Local File Upload to OSS

**Given:**
- A local audio file path (relative or absolute)
- OSS region, bucket name, and valid credentials

**When:**
- User calls `upload_audio_to_oss(local_path, region, bucket)`

**Then:**
- File is uploaded to OSS
- Public URL is returned for FunASR to access
- Upload status code is returned
- File metadata (size, checksum) is logged

#### Scenario: ASR Output Normalization

**Given:**
- Raw FunASR transcription output containing speaker, text, timestamps

**When:**
- User calls `normalize_asr_output(funasr_result)`

**Then:**
- Output is converted to standard JSON format compatible with Qwen ASR
- All fields are validated and missing values use defaults
- Timestamps are preserved in milliseconds
- Result can be directly passed to evaluation engine

### Requirement: Multi-Engine Workflow

The system SHALL enable users to select between Qwen and FunASR engines when running the evaluation workflow via CLI parameter `--asr-engine`.

#### Scenario: Specify ASR Engine via CLI

**Given:**
- `workflow.py` is invoked with audio and question bank paths

**When:**
- User passes `--asr-engine funasr` (or omits for default `qwen`)
- User provides required OSS parameters: `--oss-region` and `--oss-bucket`

**Then:**
- Workflow uses selected engine for transcription
- Audio file is uploaded (for FunASR) or processed directly (for Qwen)
- Transcription result is used in subsequent evaluation steps
- Overall workflow completes successfully

#### Scenario: Engine Selection with Parameter Validation

**Given:**
- `workflow.py` is invoked with `--asr-engine funasr`

**When:**
- User omits required OSS parameters (`--oss-region` or `--oss-bucket`)

**Then:**
- Workflow exits with clear error message
- Error message specifies which parameters are missing
- Usage help is displayed

#### Scenario: Backward Compatibility

**Given:**
- Existing scripts or workflows using old format

**When:**
- User does not specify `--asr-engine` parameter

**Then:**
- Workflow defaults to Qwen ASR (existing behavior)
- No breaking changes to command-line interface

### Requirement: Local File Upload Integration

The system SHALL provide seamless local-to-OSS upload capability as part of FunASR workflow, automatically handling file upload before transcription.

#### Scenario: Automatic Upload Before Transcription

**Given:**
- Local audio file `./audio/lecture.mp3`
- OSS credentials and FunASR engine selected

**When:**
- `workflow.py` is run with `--asr-engine funasr`

**Then:**
- File is automatically uploaded to OSS (unless already public URL)
- Upload progress/status is logged to stdout
- OSS URL is used for FunASR transcription
- Optionally delete file from OSS after transcription (configurable)

## MODIFIED Requirements

### Requirement: Evaluation Workflow

The existing evaluation workflow SHALL be extended to support multiple ASR engines while maintaining backward compatibility with the existing Qwen-only implementation.

#### New Scenario: Multi-Engine Selection

**Given:**
- User wants to run evaluation with different ASR engines

**When:**
- User invokes `workflow.py` with `--asr-engine {qwen|funasr}` and appropriate parameters

**Then:**
- Workflow routes to correct transcription engine
- Result is normalized to standard format
- Rest of evaluation pipeline remains unchanged
- Output JSON report has same structure regardless of engine

**Note:** This is an extension; existing behavior is fully preserved.

## Data Format Specification

### Standard Transcription Output Format

All transcription engines must output in this format for downstream compatibility:

```json
{
  "sentences": [
    {
      "text": "string (transcribed text)",
      "speaker": "string (spk0, spk1, etc.)",
      "start_time": "integer (milliseconds)",
      "end_time": "integer (milliseconds)",
      "word_timestamp": "array (optional, detailed token timestamps)"
    }
  ]
}
```

## API Signatures

### Core Functions in `scripts/funasr_workflow.py`

```python
def upload_audio_to_oss(
    local_path: str,
    region: str,
    bucket: str,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload local audio file to OSS.

    Returns:
        {"oss_url": str, "status_code": int, ...}
    """
    pass

def transcribe_with_funasr(
    oss_url: str,
    api_key: Optional[str] = None,
    max_retries: int = 10,
    retry_interval: int = 2
) -> str:
    """
    Transcribe audio using FunASR via OSS URL.

    Returns:
        JSON string with transcription result
    """
    pass

def normalize_asr_output(
    funasr_result: Dict[str, Any]
) -> str:
    """
    Convert FunASR output to standard format.

    Returns:
        JSON string in standard transcription format
    """
    pass
```

### Updated CLI Parameters in `workflow.py`

```
--asr-engine {qwen|funasr}      Default: qwen
--oss-region REGION              Required if asr-engine=funasr
--oss-bucket BUCKET              Required if asr-engine=funasr
--oss-endpoint ENDPOINT          Optional, auto-generated if omitted
--keep-oss-file                  Optional flag (default: False)
```

## Error Handling

### Upload Errors
- File not found: `FileNotFoundError` with clear path message
- Permission denied: `RuntimeError` with OSS credential check instructions
- Network error: Retry up to 3 times, then `RuntimeError`

### Transcription Errors
- Task submission failed: `RuntimeError` with API error details
- Task execution failed: `RuntimeError` with task ID for debugging
- Polling timeout: `TimeoutError` after max retries exceeded
- Invalid OSS URL: `ValueError` with URL validation message

### Format Errors
- Missing required fields: Use default values (e.g., spk0 for speaker)
- Invalid timestamp: Validate and log warning, but continue

## Backward Compatibility

✅ **Fully backward compatible:**
- Existing `qwen3.py` functionality unchanged
- Existing `captioner_qwen3.py` functionality unchanged
- `workflow.py` defaults to Qwen when `--asr-engine` not specified
- All new parameters are optional with sensible defaults
