# Code Improvement Plan for Gemini_annotation.py and qwen_asr.py

**Generated**: 2025-11-29
**Analysis by**: Codex GPT-5.1
**Target Scripts**: `scripts/Gemini_annotation.py`, `scripts/qwen_asr.py`

---

## Objective 1 – Cut Unnecessary Parts & Streamline Code

### Gemini_annotation.py

1. **Remove Duplicate & Unused Imports** (`lines 18, 25-44, 158`)
   - `time` is imported twice (line 18 and line 158)
   - Manual `.env` parsing (lines 25-44) should be replaced with `dotenv.load_dotenv()` from `python-dotenv`
   - **Action**: Use `python-dotenv`, remove duplicate import and manual parsing code

2. **Reduce Verbose Logging** (`lines 105-239`)
   - Currently prints full system/user prompt and every `finish_reason` detail on every call
   - This dumps thousands of lines during batch runs
   - **Action**: Gate verbose traces behind `--verbose` flag, default to concise status lines
   - Create shared helper for formatting logs instead of inline prints in every branch

3. **Remove Duplicate Fallback Functions** (`lines 242-335`)
   - Three near-identical fallback helpers exist:
     - `handle_max_tokens_error`
     - `create_simple_response` (unused)
     - `create_fallback_response` (unused)
   - Only `handle_max_tokens_error` is actually referenced
   - **Action**: Delete unused functions, consolidate logic into single `build_placeholder_response(prompt)` utility

4. **Remove Dead Code** (`lines 338-352`)
   - `save_result()` function is defined but never called
   - **Action**: Delete the function, rely on existing inline writes in `process_student_annotations`

5. **Improve Already-Processed Check** (`lines 719-847`)
   - Currently refuses to process dataset if ANY student has `4_llm_annotation.json`
   - Hard exit prevents partial reruns
   - **Action**: Add `--force` flag for full reruns, otherwise skip already-processed students quietly
   - Reuse dataset/student discovery logic from ASR script

### qwen_asr.py

6. **Collapse Duplicate Dataset Traversal** (`lines 619-699`)
   - `process_all_students`, `process_dataset`, and `process_student` duplicate logic
   - Redundant `transcribe_and_save()` helper (lines 460-497) alongside `transcribe_and_save_with_segmentation`
   - **Action**: Consolidate into one orchestrator that:
     - Discovers datasets once
     - Instantiates `QwenASRProvider` once per run
     - Always delegates to `transcribe_and_save_with_segmentation`
     - Remove redundant vocabulary/audiopath resolution code branches

---

## Objective 2 – Prompt Version Control & Editing

### Current Problems

- Prompts mixed across three sources:
  - Inline `system_instruction` (Gemini lines 545-559)
  - Single file `prompts/annotation.txt` (lines 507-509)
  - Hardcoded placeholder names (lines 73-79)
- No versioning system
- Editing prompts requires code changes
- No audit trail of prompt changes

### Proposed Solution

1. **Structured Prompt Package**
   ```
   backend_input/prompts/annotation/
   ├── v2025.01/
   │   ├── system.md           # System instruction
   │   ├── user.txt            # User prompt template
   │   └── metadata.json       # Version info (description, owner, updated_at)
   ├── v2025.02/
   │   ├── system.md
   │   ├── user.txt
   │   └── metadata.json
   └── prompts.json            # Manifest file
   ```

2. **Manifest File** (`backend_input/prompts/prompts.json`)
   - Lists available prompt versions
   - Defines default version
   - Maps placeholder names (`{{question_bank}}`, `{{student_asr}}`)
   - `Gemini_annotation.py` reads manifest at startup and validates version

3. **CLI Flags**
   - Add `--prompt-version v2025.02` flag
   - Add `--prompt-dir /path/...` flag for custom prompt directories
   - Persist version used in:
     - `4_llm_prompt_log.txt`
     - `batch_annotation_report.json`

4. **Template Renderer**
   - Replace hardcoded placeholder replacement in `build_full_prompt()`
   - Create small template renderer accepting dict of sections:
     - Question bank JSON
     - ASR text
     - Optional rubric
   - Auto-strip Markdown fences
   - Remove formatting quirks for prompt editors

5. **Documentation** (`docs/prompts.md`)
   - Document editing workflow:
     1. Copy previous version folder
     2. Edit `system.md`/`user.txt`
     3. Update `metadata.json`
     4. Run `python scripts/Gemini_annotation.py --prompt-version ... --dry-run` to validate
     5. Commit new folder
   - Keeps prompt changes in git history
   - No code touches needed for prompt edits

---

## Objective 3 – File Paths From `backend_input`

### Current Problem

All file operations use paths from project root (`archive/`, `prompts/`, etc.)
Need to redirect to `/Users/damien/Desktop/LanProject/quickfire_workflow/backend_input`

### Changes Required

1. **Define Backend Input Root**
   - Add constant at top of both scripts:
     ```python
     BACKEND_INPUT_ROOT = Path("/Users/damien/Desktop/LanProject/quickfire_workflow/backend_input")
     ```
   - Replace all `project_root / "archive"` references with `BACKEND_INPUT_ROOT / "archive"`

2. **File Path Mappings**

   **Gemini_annotation.py:**
   - Lines 375-418, 498-538, 676-685, 746-847: Dataset discovery paths
   - Line 507: `prompt_template_path` → `BACKEND_INPUT_ROOT / "prompts" / <version> / user.txt`
   - Lines 510-527: Question bank globbing → `BACKEND_INPUT_ROOT / "archive" / dataset / "_shared_context"`
   - Lines 447-470: `find_asr_file()` → use BACKEND_INPUT_ROOT
   - Line 82: `extract_text_from_asr_json()` → read from backend_input
   - Lines 599-621: Prompt logs → write to backend_input
   - Lines 637-644: `4_llm_annotation.json` → write to backend_input
   - Line 835: `batch_annotation_report.json` → write to backend_input

   **qwen_asr.py:**
   - Lines 619-699, 730-795, 896-1051: Dataset traversal paths
   - Lines 841-878: `find_audio_file()` → use BACKEND_INPUT_ROOT
   - Lines 798-839: `find_vocabulary_file()` → use BACKEND_INPUT_ROOT
   - Lines 499-612: ASR output writes → write to backend_input

3. **Helper Functions**
   - Create centralized path helpers:
     ```python
     def dataset_path(dataset_name: str) -> Path:
         return BACKEND_INPUT_ROOT / "archive" / dataset_name

     def student_path(dataset_name: str, student_name: str) -> Path:
         return dataset_path(dataset_name) / student_name

     def shared_context_path(dataset_name: str) -> Path:
         return dataset_path(dataset_name) / "_shared_context"
     ```
   - Fail fast if paths attempt to escape backend_input root

4. **CLI Configuration**
   - Add `--backend-input` CLI flag (defaults to absolute path above)
   - Both scripts resolve ALL file I/O through this base
   - Makes testing easier (can pass temp directory)
   - Prevents future hardcoded path edits

5. **Verification Helper**
   - Check required subfolders before processing:
     - `archive/`
     - `_shared_context/`
     - `1_input_audio.*` or `1_input_mp4/`
   - Log single summary of what will be read/written
   - Operators can confirm correct data set location

---

## Implementation Priority

### Phase 1 - Critical Path Changes
1. Add `BACKEND_INPUT_ROOT` constant and path helper functions
2. Update all file I/O to use backend_input paths
3. Add verification helper for required directories

### Phase 2 - Code Cleanup
1. Remove duplicate imports and dead code
2. Consolidate fallback functions
3. Add `--verbose` flag for logging
4. Add `--force` flag for reprocessing
5. Collapse duplicate dataset traversal code

### Phase 3 - Prompt System
1. Create prompt directory structure in backend_input
2. Implement manifest and template renderer
3. Add CLI flags for prompt versioning
4. Document editing workflow
5. Migrate existing prompts to new structure

---

## Testing Checklist

- [ ] Verify all file reads/writes use backend_input paths
- [ ] Test with `--backend-input` pointing to different directory
- [ ] Confirm verification helper catches missing directories
- [ ] Test `--verbose` flag reduces log output in normal mode
- [ ] Test `--force` flag allows reprocessing
- [ ] Validate prompt versioning system loads correct templates
- [ ] Run batch processing on test dataset
- [ ] Verify backward compatibility with existing data structures

---

## Next Steps

1. Review and approve this plan
2. Create backup of current scripts
3. Implement changes in phases
4. Test each phase before proceeding
5. Update documentation
