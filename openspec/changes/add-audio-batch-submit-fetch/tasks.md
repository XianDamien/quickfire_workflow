## 1. Implementation
- [ ] 扩展 `scripts/gemini_batch_audio.py`：增加 `submit`/`fetch`（以及与 ASR 对齐的状态/列表/取消，如需）
- [ ] 音频 `fetch` 生成与 ASR 一致的输出：`batch_manifest.json`、`batch_report.json`、`students/`、`4_llm_annotation.json`
- [ ] 统一错误码命名规则（ASR/音频一致）
- [ ] 统一 `token_usage` 的写入逻辑（ASR/音频所有路径补齐）
- [ ] 音频 `prompt_log.txt` 写入到 run 目录（对齐 ASR）
- [ ] 音频写入 `run_manifest.json`（对齐 ASR）
- [ ] 统一音频输出标识（`.audio` 后缀规则落地）
- [ ] 更新 `docs/how_to_test_comparison.md` 命令为 `uv run python`
- [ ] 精简对比报告为 2 个 sheet（核心指标 + 错误详情）
- [ ] 默认启用代理（未配置时使用 `http://127.0.0.1:7890`）

## 2. Testing
- [ ] 使用单个班级验证：音频 `submit` 后 `fetch` 生成完整输出
- [ ] 对比 ASR/音频输出结构一致性（字段与目录）
