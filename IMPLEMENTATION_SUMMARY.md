# Prompt Management Refactoring Implementation Summary

## Overview
Successfully refactored the Gemini annotation prompt system to use structured prompt loading with Jinja2 templating, removing ad-hoc prompt concatenation and establishing Git as the sole version control mechanism.

## Changes Made

### 1. New Directory Structure
```
prompts/
├── annotation/
│   ├── system.md        # Markdown system instruction (non-templated)
│   ├── user.txt         # Jinja2 template for user prompt
│   └── metadata.json    # Descriptive metadata (no version info)
├── prompt_loader.py     # New loader module
└── annotation.txt       # DEPRECATED (old template file)
```

### 2. New Files Created

#### `prompts/prompt_loader.py`
A structured prompt loading module providing:
- **PromptLoader class**: Loads system.md, user.txt, and metadata.json; handles Jinja2 rendering
- **PromptArtifacts dataclass**: Container for loaded prompt components
- **PromptContextBuilder helper**: Builds consistent context dictionary for template rendering

Key features:
- Fails fast on missing files with detailed error messages
- Jinja2 environment configured with `trim_blocks=True` and `lstrip_blocks=True` for predictable whitespace
- No version management, fallback logic, or runtime switches
- Metadata is purely descriptive (owner, description, tags, updated_at, contact, notes)

#### `prompts/annotation/system.md`
Extracted from hardcoded system instruction in Gemini_annotation.py. Contains:
- Role definition (AI assistant specializing in data processing and text analysis)
- Background on teacher/student audio transcription structure
- Grading logic (A: 0 errors, B: 1-2 errors, C: 3+ errors)
- Special handling notes (detecting duplicate answers, error re-review)

#### `prompts/annotation/user.txt`
Jinja2 template with variables:
- `{{ question_bank_json }}` - Question bank content
- `{{ student_asr_text }}` - Student ASR transcription
- `{{ dataset_name }}` - Dataset identifier (optional context)
- `{{ student_name }}` - Student identifier (optional context)
- `{{ metadata }}` - Prompt metadata (optional context)

Processing instructions and output format specifications preserved from original.

#### `prompts/annotation/metadata.json`
Descriptive metadata (non-versioned):
```json
{
  "description": "Gemini annotation prompt for extracting student responses...",
  "owner": "data-ops@lan",
  "updated_at": "2025-11-30T12:00:00+08:00",
  "tags": ["annotation", "gemini", "student-response-extraction", "vocabulary"],
  "notes": "Keep NO_ANSWER and MEANING_ERROR detection logic aligned with rubric",
  "contact": ["pm@lan"]
}
```

### 3. Refactored `scripts/Gemini_annotation.py`

#### Imports Added
```python
sys.path.insert(0, str(Path(__file__).parent.parent / "prompts"))
from prompt_loader import PromptLoader, PromptContextBuilder
```

#### Functions Removed
- `load_prompt_template()` - Replaced by PromptLoader
- `build_full_prompt()` - Replaced by Jinja2 template rendering

#### Functions Added
- `find_question_bank(shared_context_dir, dataset_name)` - Unified question bank discovery
  - Supports patterns: R3-14-D4*.json, R1-65*.json, R*.json
  - Excludes vocabulary files
  - Prepared for future /questionbank path support

#### Major Changes to `process_student_annotations()`
**Before:**
```python
prompt_template = load_prompt_template(prompt_template_path)
question_bank = load_file_content(str(question_bank_path))
system_instruction = """# 角色\n你是一个..."""  # Hardcoded
full_prompt = build_full_prompt(prompt_template, question_bank, student_asr_text)
```

**After:**
```python
prompt_loader = PromptLoader(str(prompt_dir))
prompt_context = PromptContextBuilder.build(
    question_bank_json=question_bank,
    student_asr_text=student_asr_text,
    dataset_name=dataset_name,
    student_name=student_name,
    metadata=prompt_loader.metadata
)
system_instruction = prompt_loader.system_instruction
full_prompt = prompt_loader.render_user_prompt(prompt_context)
```

#### Enhanced Prompt Logging
Added to `4_llm_prompt_log.txt`:
- `Git Commit`: Current commit hash for audit trail
- `题库文件`: Question bank filename discovered at runtime
- `PROMPT METADATA`: Full metadata from metadata.json (description, owner, tags, etc.)
- Maintains all existing logging (system instruction, user prompt)

### 4. Question Bank Discovery (Future-Ready)

Current implementation:
```python
# Searches archive/{dataset}/_shared_context/ with patterns
for pattern in ["R3-14-D4*.json", "R1-65*.json", "R*.json"]:
    # Find first matching file excluding vocabulary
```

Future support stub:
```python
# Prepared for /questionbank directory structure
# Example: /questionbank/{dataset_name}/ or /questionbank/shared/
# Can be activated when users migrate question banks
```

## Technical Design Decisions

### Why No Folder-Based Versioning?
- Git history is the authoritative version control mechanism
- Simpler to maintain and understand
- Prevents confusion from multiple prompt versions
- Forces explicit commits for prompt changes

### Why Jinja2?
- Lightweight and easy to integrate
- Supports all needed variables and conditional logic
- Predictable whitespace handling (trim_blocks, lstrip_blocks)
- Industry standard for template-based workflows

### Why Separate system.md and user.txt?
- Clear separation of concerns
- System instructions are typically more stable
- User templates change more frequently
- Easier to audit and review diffs

### Why Metadata in JSON?
- Structured, queryable format
- Easy to extend with new fields
- Can be used for filtering/organization without requiring versioning
- Audit trail via git commits

## Validation

### Unit Tests Passed
✓ PromptLoader initializes and loads all files
✓ Metadata JSON parses correctly
✓ Context building produces expected dictionary
✓ User prompt renders with all variables
✓ System instruction loads without modification
✓ Script syntax validation successful

### Error Handling
- Missing prompt files: `FileNotFoundError` with explicit file path
- Malformed metadata.json: `json.JSONDecodeError` with details
- Template rendering errors: `RuntimeError` with template error information
- Missing context variables: `jinja2.UndefinedError` caught as `RuntimeError`

## Usage

### Basic Usage (Unchanged from User Perspective)
```bash
# Process all datasets
python3 scripts/Gemini_annotation.py

# Process specific dataset
python3 scripts/Gemini_annotation.py --dataset Zoe51530-9.8

# Process single student
python3 scripts/Gemini_annotation.py --dataset Zoe51530-9.8 --student Oscar
```

### Modifying Prompts
1. Edit `prompts/annotation/system.md` and/or `prompts/annotation/user.txt`
2. Optionally update `prompts/annotation/metadata.json`
3. Commit all three files together:
   ```bash
   git add prompts/annotation/
   git commit -m "feat(prompts): adjust annotation prompt for Q4 exam"
   ```
4. Future runs automatically use updated prompts

### Auditing Prompt Usage
Check `4_llm_prompt_log.txt` in any student directory:
- Git commit hash identifies exact prompt version used
- Metadata shows prompt description, owner, and update timestamp
- Full system instruction and rendered user prompt preserved for debugging

## Migration Path from Old System

If there are existing annotation.txt files in different formats:
1. Extract system instruction → `prompts/annotation/system.md`
2. Extract user template → `prompts/annotation/user.txt`
3. Create appropriate `prompts/annotation/metadata.json`
4. Update git history with single commit
5. Script automatically uses new structure

## Future Enhancements

### 1. Multiple Prompt Variants (Branch-Based)
```bash
# On a feature branch
git checkout -b experiment/new-grading-logic
# Edit prompts/annotation/system.md and user.txt
# Run tests on experimental dataset
git commit ...
# Merge only when approved
```

### 2. Support for /questionbank Directory
Activate the future-ready code in `find_question_bank()`:
```python
# Check /questionbank/{dataset_name}/ for question banks
questionbank_root = Path("/Users/damien/Desktop/LanProject/quickfire_workflow/questionbank")
if dataset_name:
    dataset_qb = questionbank_root / dataset_name
    # Search there if shared_context not found
```

### 3. Prompt Testing Framework
- Load multiple prompt versions from different git commits
- Run parallel processing with each
- Compare results quantitatively

### 4. Metadata-Based Filtering
- Tag prompts by skill level, domain, etc.
- Select prompts programmatically based on dataset characteristics
- Maintain metadata index for quick lookups

## Files Modified

1. `scripts/Gemini_annotation.py` - Refactored to use PromptLoader
2. `prompts/prompt_loader.py` - NEW: Structured prompt loading module
3. `prompts/annotation/system.md` - NEW: System instruction template
4. `prompts/annotation/user.txt` - NEW: User prompt Jinja2 template
5. `prompts/annotation/metadata.json` - NEW: Prompt metadata

## Files Preserved

- `prompts/annotation.txt` - DEPRECATED: Old template file (kept for reference)
- All other scripts and modules unchanged (backward compatible)

## Testing Strategy

Since archive directories are typically git-ignored (contain large datasets), end-to-end testing should be performed on:
1. Development datasets with known structure
2. Datasets stored outside git (OSS, local paths, etc.)
3. Mock datasets for CI/CD pipelines

The refactored code has been validated to:
- Load prompts correctly
- Render Jinja2 templates properly
- Pass syntax validation
- Import without errors
- Maintain all existing CLI interfaces
