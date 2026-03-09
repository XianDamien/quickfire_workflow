---
name: quickfire-annotation-backfill
description: This skill should be used when consolidating Quickfire archive results, identifying untested students from consolidated_grades.xlsx, and backfilling missing 4_llm_annotation.json files by rerunning the annotation pipeline for specific archive batches/students.
---

# Quickfire Annotation Backfill

## Overview

Summarize archive results, find untested students, rerun annotation for missing students, and regenerate the consolidated report.

## Workflow

### 1) Refresh consolidated report

Run the archive consolidator to regenerate `archive/consolidated_grades.xlsx`.

```bash
python3 scripts/consolidate_grades.py
```

### 2) Identify untested students

Read the `未测试数据` sheet in `archive/consolidated_grades.xlsx`. Each row contains:
- 批次 (archive batch folder name, e.g., `Zoe41900_2025-09-08`)
- 学生 (student name)
- 原因 (e.g., missing `4_llm_annotation.json`)

Treat `_batch_runs`, `runs`, `reports`, `_shared_context`, and hidden folders as non-students.

### 3) Rerun annotation for missing students

Use the main pipeline to rerun annotation for each untested student. Default annotator is in `scripts/annotators/config.py`.

```bash
uv run python scripts/main.py --archive-batch <BATCH> --student <STUDENT>
```

Optional flags:
- `--annotator <model>` to override the default model
- `--force` to redo stages even if outputs exist
- `--dry-run` to preview without execution

Example:
```bash
uv run python scripts/main.py --archive-batch Niko60900_2025-11-14 --student Yiyi
```

### 4) Rebuild and verify

Re-run the consolidator and confirm the untested list shrinks.

```bash
python3 scripts/consolidate_grades.py
```

Verify that the new run created:
`archive/<batch>/<student>/runs/<annotator>/<run_id>/4_llm_annotation.json`

## Notes

- Latest annotation is determined by run directory timestamp (`YYYYMMDD_HHMMSS`) with fallback to file mtime.
- Running annotation requires valid API credentials and network access for the selected model.
