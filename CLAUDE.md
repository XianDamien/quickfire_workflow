<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

English pronunciation assessment system: Audio → ASR transcription → LLM grading. Processes student recordings, matches answers against question banks, outputs A/B/C grades.

## Commands

```bash
uv sync                                                    # Install deps
python3 scripts/main.py --archive-batch <batch_id>         # Full pipeline
python3 scripts/main.py --archive-batch <batch_id> --student <name>
python3 scripts/main.py --archive-batch <batch_id> --only qwen_asr      # Single stage
python3 scripts/main.py --archive-batch <batch_id> --annotator qwen-max # Switch annotator
python3 scripts/main.py --archive-batch <batch_id> --dry-run            # Preview
```

Stages: `audio` | `qwen_asr` | `timestamps` | `cards`
Annotators: `gemini-3-pro-preview` (default) | `qwen-max` | `qwen3-max`
System deps: `ffmpeg`, `ffprobe`

## Architecture

```
audio → qwen_asr → timestamps → cards
           ↓            ↓          ↓
     2_qwen_asr.json  3_asr_*.json  4_llm_annotation.json
```

| Module | Purpose |
|--------|---------|
| `scripts/main.py` | DAG pipeline entry |
| `scripts/asr/qwen.py` | Qwen3-ASR (auto-segments long audio) |
| `scripts/asr/funasr.py` | FunASR timestamps |
| `scripts/annotators/` | LLM graders (Gemini/Qwen) |
| `prompts/annotation/` | Grading prompt templates |

**Data layout:**
```
archive/{ClassCode}_{Date}/{Student}/
├── 1_input_audio.mp3
├── 2_qwen_asr.json
├── 3_asr_timestamp.json
└── runs/{annotator}/{run_id}/4_llm_annotation.json
```

## Testing

⚠️ **Use real audio files only. Never mock ASR data.**
- Use `--dry-run` to validate pipeline logic
- After prompt changes, run annotation to verify output before commit

## Prompt Management

- Update `metadata.json` whenever prompt files change

### Commit Rules
- **Commit directly**: Minor edits (typos, timestamp updates, docs only)
- **Test first**: Substantive prompt changes → run annotation, verify output, then commit
- Commit prompt + metadata.json together as atomic unit
