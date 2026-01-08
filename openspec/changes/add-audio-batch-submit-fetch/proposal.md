# Change: Add submit/fetch workflow for audio batch runs and align outputs

## Why
当前音频批处理只能同步等待，无法先提交后统一拉取；音频与 ASR 的输出结构也不一致，导致统计与对比成本高。

## What Changes
- 新增音频批处理的 `submit`/`fetch` 以支持先提交再统一拉取。
- 音频与 ASR 的输出结构对齐：统一 `batch_manifest.json`、`batch_report.json`、`students/`、`run_manifest.json`、`prompt_log.txt` 的位置与字段。
- 统一错误码命名与 token_usage 写入逻辑（所有路径都补齐 token 统计）。
- 统一音频输出标识：音频输出在相同结构下增加 `.audio` 后缀（用于区分音频方案）。
- 对比报告结构精简：`compare_asr_audio.py` 输出 2 个 sheet（核心指标 + 错误详情）。
- 代理默认启用：未显式配置时，默认使用 `http://127.0.0.1:7890`。
- 文档命令统一为 `uv run python`。

## Impact
- Affected code: `scripts/gemini_batch_audio.py`, `scripts/gemini_batch.py`, `scripts/compare_asr_audio.py`, `scripts/common/runs.py`, `docs/how_to_test_comparison.md`
- Data/output: `_batch_runs/*` 与 `archive/*/runs/*` 的输出结构将更一致（新增或规范化字段）
- Reporting: 对比报告从 3 个 sheet 精简为 2 个 sheet
