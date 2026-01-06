# Spec: Qwen Annotator Integration

## Why

Current system only supports Google Gemini for LLM-based grading. Adding Qwen annotator provides:
- **Diversity**: Multiple LLM options for quality comparison
- **Availability**: Fallback when Gemini API is unavailable
- **Cost Optimization**: Different pricing models for different needs
- **Compliance**: Domestic model option for certain requirements

The existing architecture already reserves the Qwen interface (`scripts/annotators/__init__.py:105-109`) but raises `NotImplementedError`. Implementing this will complete the multi-LLM support architecture.

## Overview
Add Qwen Annotator implementation to support using Alibaba Cloud Qwen series models (qwen-max, qwen-max-latest, qwen3-max) for student assignment grading, providing a parallel alternative to the existing Gemini Annotator.

## NEW Requirements

### Requirement: Qwen Annotator Class Implementation
**ID**: qwen-annotator-class

The system SHALL implement a `QwenAnnotator` class that inherits from `BaseAnnotator` and supports Qwen series models for student assignment annotation.

**Implementation Details**:
- Class location: `scripts/annotators/qwen.py`
- Inheritance: `class QwenAnnotator(BaseAnnotator)`
- Supported models: `qwen-max`, `qwen-max-latest`, `qwen3-max`
- API: Uses `dashscope.Generation.call()` with DashScope API

**Constructor Parameters**:
```python
def __init__(
    self,
    model: str = "qwen-max",
    temperature: float = 0.2,
    max_output_tokens: int = 16384,
    max_retries: int = 5,
    retry_delay: int = 5,
)
```

**Required Behavior**:
- MUST read `DASHSCOPE_API_KEY` from environment variables
- MUST raise `ValueError` if API key is not set
- MUST store model name in both `self.model` and `self.name`
- MUST initialize all configuration parameters

#### Scenario: Successful initialization
Given environment variable `DASHSCOPE_API_KEY` is set
When initializing `QwenAnnotator(model="qwen-max")`
Then the instance should be created successfully
And `self.model` should equal "qwen-max"
And `self.api_key` should contain the API key from environment

#### Scenario: Missing API key
Given environment variable `DASHSCOPE_API_KEY` is not set
When attempting to initialize `QwenAnnotator()`
Then a `ValueError` should be raised
And the error message should mention "DASHSCOPE_API_KEY 环境变量未设置"

---

### Requirement: Qwen API Integration
**ID**: qwen-api-integration

The `QwenAnnotator.annotate()` method SHALL call the DashScope API with proper message formatting and retry logic.

**API Call Format**:
```python
response = dashscope.Generation.call(
    model=self.model,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    temperature=self.temperature,
    max_tokens=self.max_output_tokens,
    result_format="message"
)
```

**Required Behavior**:
- MUST use rendered prompts from `_render_prompts(input_data)`
- MUST implement retry logic (max 5 attempts, 5 second delay)
- MUST extract response text from `response.output.choices[0].message.content`
- MUST call `_parse_response()` to parse JSON from response
- MUST call `_validate_output()` to validate parsed JSON
- MUST return `AnnotatorOutput` with all required fields

#### Scenario: Successful API call
Given valid `AnnotatorInput` with questionbank and ASR text
When calling `annotate(input_data)`
Then the method should render system and user prompts
And call `dashscope.Generation.call()` with correct parameters
And extract response text successfully
And return `AnnotatorOutput` with `parsed_json` field populated

#### Scenario: API call with retry
Given first API call fails with transient error
When calling `annotate(input_data)`
Then the method should retry up to 5 times
And wait 5 seconds between retries
And succeed on subsequent attempt

#### Scenario: API call exhausts retries
Given all 5 API call attempts fail
When calling `annotate(input_data)`
Then the method should raise the last exception
And allow it to propagate to caller

---

### Requirement: Prompt Reuse and Output Format Compatibility
**ID**: prompt-output-compatibility

The Qwen Annotator MUST reuse existing prompt templates and produce output compatible with the existing validation logic.

**Prompt Reuse**:
- MUST use `prompts/annotation/system.md` for system prompt
- MUST use `prompts/annotation/user.md` for user prompt
- MUST NOT modify any prompt template content
- MUST use `_render_prompts()` helper method

**Output Format**:
The parsed JSON MUST contain:
- `final_grade_suggestion` (str): "A" | "B" | "C"
- `mistake_count` (dict): `{"errors": int}`
- `annotations` (list): Array of annotation objects

Each annotation object MUST contain:
- `card_index` (int)
- `question` (str)
- `expected_answer` (str)
- `related_student_utterance` (dict):
  - `detected_text` (str)
  - `issue_type` (str): "NO_ANSWER" | "MEANING_ERROR" | null

#### Scenario: Prompt rendering
Given `AnnotatorInput` with questionbank JSON and ASR text
When calling `_render_prompts(input_data)`
Then system prompt should be loaded from `prompts/annotation/system.md`
And user prompt should be loaded from `prompts/annotation/user.md`
And user prompt should contain `{{ question_bank_json }}` replaced with actual JSON
And user prompt should contain `{{ student_asr_text }}` replaced with actual ASR text

#### Scenario: Output validation
Given Qwen API returns JSON response
When calling `_validate_output(parsed_json)`
Then validation should pass if all required fields are present
And should raise exception if any required field is missing
And validation logic should be identical to Gemini annotator

---

### Requirement: Archive Student Processing
**ID**: archive-student-processing

The `QwenAnnotator.run_archive_student()` method SHALL process a student's assignment and save results to the run directory.

**Required Behavior**:
- MUST load ASR result from `{archive_dir}/{student}/2_qwen_asr.json`
- MUST load questionbank from `questionbank/{progress}.json`
- MUST call `annotate()` with loaded data
- MUST save result to `{run_dir}/4_llm_annotation.json`
- MUST save prompts to `{run_dir}/prompt_log.txt`
- MUST print processing time statistics
- MUST return processing result with status

**Output Files**:
1. `4_llm_annotation.json`: Complete annotation result
2. `prompt_log.txt`: Contains:
   ```
   === System Prompt ===
   [system prompt content]

   === User Prompt ===
   [user prompt content]
   ```

#### Scenario: Successful student processing
Given archive batch "Zoe51530_2025-09-08" and student "Stefan"
And ASR file exists at `archive/Zoe51530_2025-09-08/Stefan/2_qwen_asr.json`
And questionbank file exists at `questionbank/R3-14-D4.json`
When calling `run_archive_student("Zoe51530_2025-09-08", "Stefan", run_dir)`
Then method should load both files successfully
And call `annotate()` with correct input data
And save `4_llm_annotation.json` to run directory
And save `prompt_log.txt` to run directory
And print "✓ Stefan: 已保存到 ..." to console

#### Scenario: Missing ASR file
Given archive batch and student name
But ASR file does not exist
When calling `run_archive_student()`
Then method should raise appropriate error
And error message should indicate missing ASR file

---

### Requirement: Annotator Registration
**ID**: annotator-registration

The `get_annotator()` function SHALL support Qwen annotator creation through proper provider routing.

**Modified Behavior** (`scripts/annotators/__init__.py:105-109`):
```python
# OLD (raises NotImplementedError)
if provider == "qwen":
    raise NotImplementedError(...)

# NEW (returns QwenAnnotator instance)
if provider == "qwen":
    from .qwen import QwenAnnotator

    # 规范化模型名称
    if model in ["qwen", "qwen-max"]:
        model = "qwen-max"

    return QwenAnnotator(model=model, **kwargs)
```

**Required Behavior**:
- MUST support `get_annotator("qwen-max")`
- MUST support `get_annotator("qwen:qwen-max-latest")`
- MUST support `get_annotator("qwen3-max")`
- MUST normalize "qwen" to "qwen-max"
- MUST pass through additional kwargs to constructor

#### Scenario: Get Qwen annotator by short name
Given no provider prefix
When calling `get_annotator("qwen-max")`
Then should detect provider as "qwen"
And import `QwenAnnotator`
And return instance with model="qwen-max"

#### Scenario: Get Qwen annotator with provider prefix
Given provider:model format
When calling `get_annotator("qwen:qwen3-max")`
Then should parse provider as "qwen"
And model as "qwen3-max"
And return `QwenAnnotator` instance with correct model

#### Scenario: Model name normalization
Given short name "qwen"
When calling `get_annotator("qwen")`
Then should normalize to "qwen-max"
And return `QwenAnnotator(model="qwen-max")`

---

### Requirement: CLI Integration
**ID**: cli-integration

The main script SHALL support `--annotator qwen-max` parameter for selecting Qwen annotator during cards stage.

**Command Example**:
```bash
python scripts/main.py \
    --archive-batch Zoe51530_2025-09-08 \
    --student Stefan \
    --only cards \
    --annotator qwen-max
```

**Required Behavior**:
- MUST accept "qwen-max", "qwen-max-latest", "qwen3-max" as valid annotator names
- MUST create run directory under `runs/qwen-max/`
- MUST print "使用 annotator: qwen-max" during execution
- MUST work identically to `--annotator gemini-2.5-pro`

#### Scenario: CLI with Qwen annotator
Given command with `--annotator qwen-max`
When running main script
Then should call `get_annotator("qwen-max")`
And create run directory `runs/qwen-max/Zoe51530_2025-09-08_Stefan_{timestamp}/`
And save outputs to this directory

---

## MODIFIED Requirements

### Requirement: Multi-Provider Architecture
**ID**: multi-provider-architecture

**Previous Behavior**:
- Gemini annotator was the only implemented provider
- Qwen interface was reserved but not implemented

**New Behavior**:
- MUST support both Gemini and Qwen providers
- MUST maintain identical interface through `BaseAnnotator`
- MUST allow easy addition of future providers (OpenAI, etc.)

#### Scenario: Provider switching
Given both Gemini and Qwen annotators available
When switching `--annotator` parameter
Then should seamlessly switch between providers
And maintain identical output format
And require no code changes in calling code

---

## Implementation Notes

### Code Organization
- **New File**: `scripts/annotators/qwen.py` (~200 lines)
- **Modified File**: `scripts/annotators/__init__.py` (lines 105-109, docstrings)
- **Modified File**: `scripts/README.md` (add usage examples)

### Key Dependencies
- `dashscope` SDK (already installed for ASR)
- `DASHSCOPE_API_KEY` environment variable (already in use)
- Existing prompt templates (no changes)
- Existing JSON validation logic (reused)

### Testing Strategy
- Use real audio files from `archive/Zoe51530_2025-09-08/Stefan/`
- Use existing ASR result `2_qwen_asr.json`
- Verify output against existing validation logic
- NO mock data allowed
- Compare with Gemini output for quality validation

### Non-Functional Constraints
- MUST NOT modify any prompt templates
- MUST NOT change existing Gemini annotator behavior
- MUST NOT add fallback mechanisms in development phase
- MUST maintain identical output format to Gemini
- MUST follow existing code style (中文注释和日志)
