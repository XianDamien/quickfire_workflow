Couldn't write to `docs/prompt_management_implementation_plan.md` because the sandbox is read-only (all edit attempts were blocked with “writing outside of the project; rejected by user approval settings”). Please copy the revised plan below into that file:

```
**Implementation Plan**
- scripts/Gemini_annotation.py currently loads `prompts/annotation.txt`, injects the question bank JSON (picked dynamically from `_shared_context` via patterns like `R3-14-D4*.json`, `R1-65*.json`, `R*.json` excluding vocabulary files), builds a fixed system instruction string, and logs prompts per student. We will preserve that dynamic question bank discovery and logging behavior while replacing the ad-hoc prompt-loading code with a structured loader that reads a single pair of prompt files plus metadata. Git remains the sole version-control mechanism; once prompts change, system/user templates and metadata must be updated together inside the same commit.

**Prompt Files**
- Directory layout becomes:
  ```
  backend_input/prompts/annotation/
    system.md        # Markdown Gemini system prompt
    user.txt         # Jinja2 template rendered for each student
    metadata.json    # Non-version metadata (owner, updated_at, tags, description, etc.)
  ```
- No folder-based version directories, no manifests, and no fallback copies. Git history tracks every change. Any modification to `user.txt` must be accompanied by the corresponding `system.md` update (enforced via code review + tests that load both files together).
- `user.txt` keeps Jinja2 templating with the contexts already available in the script (`question_bank_json`, `student_asr_text`, `dataset_name`, `student_name`, `guidance`, `metadata`, etc.). We’ll configure Jinja2 with `trim_blocks=True` and `lstrip_blocks=True` so whitespace stays predictable.

**Metadata**
- `metadata.json` is retained for descriptive fields only; it no longer contains version identifiers. Example schema:
  ```json
  {
    "description": "Gemini annotation prompt tuned for Q4 speaking exams",
    "owner": "data-ops@lan",
    "updated_at": "2025-03-21T10:05:11+08:00",
    "tags": ["annotation", "gemini", "r3-runs"],
    "notes": "Keep NO_ANSWER logic aligned with rubric v3",
    "contact": ["pm@lan"]
  }
  ```
- No question bank paths or filenames live here; those continue to be inferred at runtime from the dataset’s `_shared_context` folder.

**Prompt Loader Architecture**
- Add `backend_input/prompts/prompt_loader.py` with:
  - `PromptArtifacts` dataclass (`system_text`, `user_template`, `metadata`).
  - `PromptLoader` class that:
    - Accepts a base directory (default `backend_input/prompts/annotation`).
    - Loads `system.md`, `user.txt`, and `metadata.json` (UTF-8) during initialization.
    - Builds a single `jinja2.Environment` per loader for fast re-rendering.
    - Provides `render_user_prompt(context: dict)` and `system_instruction` accessors.
  - `PromptContextBuilder` helper that assembles the current context dictionary (question bank JSON, student ASR text, dataset/student metadata, optional `guidance`, `metadata` itself). This ensures both prompt files are updated and consumed together.

**Gemini_annotation.py Updates**
- Replace `load_prompt_template` and the inline `system_instruction` with:
  ```python
  prompt_loader = PromptLoader(project_root / "backend_input" / "prompts" / "annotation")
  prompt_context = build_prompt_context(question_bank, student_asr_text, dataset_name, student_name, metadata=prompt_loader.metadata)
  system_instruction = prompt_loader.system_instruction
  full_prompt = prompt_loader.render_user_prompt(prompt_context)
  ```
- Remove `build_full_prompt`, the legacy template path, the version manifest, and all fallback logic. Missing prompt files should raise `RuntimeError` or `FileNotFoundError` with explicit detail (e.g., which file is absent).
- Keep the existing CLI interface, but drop `--prompt-version`/fallback references entirely. If future overrides are needed, they will be handled via git branches rather than runtime switches.
- When logging to `4_llm_prompt_log.txt`, add metadata details (at least `description`, `owner`, `updated_at`, `tags`) so we can audit which prompt revision produced each output. Because prompts are no longer versioned via folders, the log should include the latest git commit hash retrieved once per run.

**Question Bank Discovery**
- Preserve the current dynamic lookup from `_shared_context` that prioritizes `R3-14-D4*.json`, then `R1-65*.json`, then `R*.json` while skipping vocabulary files. The loader must receive the exact JSON content returned by this logic. No pointer to the question bank is stored in `metadata.json`, and no fallback question bank is hardcoded.

**Error Handling & Logging**
- Development builds must fail fast: if any prompt component, question bank, ASR file, or rendered prompt step fails, raise a detailed exception and surface it to the CLI (no fallback to prior prompts or generic “something went wrong” messaging). Enrich errors with file paths and hints for missing resources.
- Logging continues to store the rendered prompt, the system instruction, and metadata. Also log the question bank filename discovered during runtime to aid debugging while keeping the discovery logic dynamic.

**Testing Strategy**
- New unit tests under `tests/prompts/test_prompt_loader.py`:
  1. `test_loader_reads_single_directory`: ensures `PromptLoader` raises descriptive errors if `system.md`, `user.txt`, or `metadata.json` are missing.
  2. `test_render_user_prompt`: validates Jinja2 rendering and confirms that updates to `system.md`/`user.txt` are consumed together.
  3. `test_metadata_schema`: checks required metadata keys (description, owner, updated_at).
  4. `test_question_bank_discovery`: regression tests for `scripts/Gemini_annotation.py` ensuring `_shared_context` patterns still work (use temporary directories with filenames like `R3-14-D4.json`, `R1-65.json`, plus a vocabulary file that must be ignored).
  5. `test_fail_fast_behavior`: simulate missing prompt files to assert that RuntimeError includes the missing path instead of falling back.
- Optional snapshot/regression tests on `full_prompt` output to catch unintended prompt drift.

**Next Steps**
1. Create `backend_input/prompts/annotation/system.md`, `user.txt` (Jinja), and `metadata.json`, migrating content from the current inline string and `prompts/annotation.txt`.
2. Implement `PromptLoader` + `PromptContextBuilder`, update `scripts/Gemini_annotation.py` to consume them, and remove `prompts.json`, version folders, and all fallback code.
3. Expand the log writer to include metadata and git commit info.
4. Add/adjust tests described above and update documentation (README, docs/gemini_prompt_logging_implementation.md) to reflect the single-directory workflow.
5. Remove obsolete prompt files/manifest references from the repo once the new loader is verified.
```

Let me know once write access is available and I can save this directly into `docs/prompt_management_implementation_plan.md`.