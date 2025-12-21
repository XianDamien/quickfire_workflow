# Legacy Scripts (Archived)

**Status**: DEPRECATED - For reference only, no compatibility guaranteed.

## Migrated Scripts

| Script | Migrated To | Status |
|--------|-------------|--------|
| `qwen_asr.py` | `scripts/main.py` + `scripts/asr/qwen.py` | Archived |
| `funasr.py` | `scripts/main.py` + `scripts/asr/funasr.py` | Archived |
| `Gemini_annotation.py` | `scripts/main.py` + `scripts/annotators/` | Archived |

## New Entry Point

All functionality is now available through the unified entry point:

```bash
# Full pipeline (default --target cards)
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08

# Text transcription only (qwen_asr)
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --target qwen_asr

# Timestamps only
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --target timestamps

# Annotation only (cards)
python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --only cards
```

## Why Archived?

1. **Unified Entry Point**: `main.py` now orchestrates the entire DAG pipeline
2. **Direct Provider Calls**: No subprocess overhead - providers called directly
3. **Consistent Interface**: Single CLI for all stages
4. **Better Error Handling**: Centralized error handling and reporting

## Do Not Use

These scripts are kept for historical reference only. They may:
- Have outdated imports
- Reference non-existent paths
- Produce incompatible output formats

For production use, always use `python3 scripts/main.py`.
