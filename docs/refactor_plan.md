 下面是基于当前仓库现状（scripts/qwen_asr.py / scripts/funasr.py / scripts/
  Gemini_annotation.py / prompts/prompt_loader.py / archive/{dataset_id}/metadata.json）的“最小改
  动、分阶段”执行计划，具体到要改哪些文件/函数。

  ## Phase 1（目标：端到端跑通 1 次；严格失败；不改上游产物形态）

  目标：跑 audio -> qwen_asr -> funasr_timestamp -> gemini_annotate，任何缺依赖/字段缺失立刻失败
  （不再把“(无时间戳数据)”喂给模型）。

  1. 强制 student_asr_with_timestamp 为必填（消灭 fallback 根因）

  - 改 prompts/prompt_loader.py：PromptContextBuilder.build(...)
      - 移除 student_asr_with_timestamp 的默认占位（目前会写成 "(无时间戳数据)"）
      - 若为空/None：直接 raise ValueError("缺少 student_asr_with_timestamp（依赖
        3_asr_timestamp.json）")

  2. Gemini 标注强依赖 3_asr_timestamp.json，缺就失败

  - 改 scripts/Gemini_annotation.py：process_archive_student_annotation(...)
      - 3_asr_timestamp.json 不存在：直接报错并退出（建议默认 fail-fast）
      - 调用 extract_timestamp_text_from_asr_json(...) 后若为空：直接失败（说明 sentences 为空或
        字段缺失）
  - 改 scripts/Gemini_annotation.py：extract_timestamp_text_from_asr_json(...)
      - 现在对 FileNotFoundError/JSONDecodeError 返回 "" 的行为要改成 抛异常（严格失败）
      - 增加结构校验：必须有 transcripts[0].sentences[*].begin_time/end_time/text，且 begin_time/
        end_time 为 int(ms)

  3. 标注输出校验：任何 card_timestamp == null 直接失败

  - 改 scripts/Gemini_annotation.py：在解析 api_result 后增加校验
      - 校验 annotations[*].card_timestamp 必须是 MM:SS 且非空
      - 不通过：保存原始输出到本次 run 目录（便于排错），并退出失败（你要求严格失败）

  4. FunASR 产物保证满足下游契约，否则不落盘/报错

  - 改 scripts/funasr.py：process_archive_student_local(...)
      - result.output.get('sentences') 为空：视为失败，不写 3_asr_timestamp.json（避免产出“看似存
        在但不可用”的文件）

  验收（手动）

  - 确认 archive/{dataset_id}/metadata.json 存在且 items 正确（你给的 schema）
  - 跑：
      - python3 scripts/qwen_asr.py --archive-batch <dataset_id> --student <student>
      - python3 scripts/funasr.py --archive-batch <dataset_id> --student <student>
      - python3 scripts/Gemini_annotation.py --archive-batch <dataset_id> --student <student>
  - 若缺 3_asr_timestamp.json / sentences 空 / 模型输出时间戳为 null：必须直接失败并给清晰错误

  ———

  ## Phase 2（目标：可复现；run_manifest 落地；不改变上游产物）

  目标：每次标注运行生成 run_manifest.json（替换/扩展现在的 run_metadata.json），记录模型/Prompt/
  输入/代码版本与耗时。

  1. 把 scripts/Gemini_annotation.py 的 run_metadata.json 升级为 run_manifest.json

  - 改 scripts/Gemini_annotation.py：写 manifest 时补齐：
      - annotator_name：直接取代码里实际 model='gemini-2.5-pro'
      - prompt：prompts/annotation/system.md、prompts/annotation/user.md 路径 + rendered prompt
        sha256
      - inputs：1_input_audio.mp3、2_qwen_asr.json、3_asr_timestamp.json、questionbank/
        {progress}.json 的 sha256
      - code.git_commit：已存在，补 dirty（可选）
      - timing.duration_ms（开始/结束时间）

  2. cards 产物写入最小 meta（引用输入版本信息）

  - 改 scripts/Gemini_annotation.py：输出 JSON 顶层增加 file_id（你现有 backend_output 已有该字
    段）+ meta.run_id/annotator_name/inputs[*].sha256

  ———

  ## Phase 3（目标：模块化；ASR/LLM 可替换；脚本变薄）

  目标：ASR 与 LLM 成为独立模块，便于后续替换不同模型；现有脚本 CLI 继续可用（最小改动迁移）。

  1. 新增包目录（示例）：quickfire/

  - quickfire/asr/qwen.py：封装现有 QwenASRProvider（从 scripts/qwen_asr.py 抽出核心类/函数）
  - quickfire/asr/funasr.py：封装 FunASR timestamp 生成（从 scripts/funasr.py 抽出）
  - quickfire/annotators/gemini.py：封装 Gemini 调用 + 输出校验（从 scripts/Gemini_annotation.py
    抽出）
  - quickfire/contracts/：放“schema 校验函数”（复用 Phase 1/2 的校验逻辑，避免散落在脚本里）

  2. scripts/*.py 变成薄 CLI wrapper

  - 保持原命令不变，但内部调用 quickfire/... 模块

  ———

  ## Phase 4（目标：一个入口 + 开关；按目标产物反推执行；A/B 不覆盖）

  目标：实现你要的 CLI 体验与 runs 分层。

  1. 新增统一入口：scripts/qf.py（或根命令模块）

  - 默认：--target cards，自动检查缺失节点并执行
  - 开关：--force、--only qwen_asr|funasr|annotate、--dry-run、--until timestamps

  2. 产物分层落地（不覆盖）

  - 输出路径改为：archive/{dataset_id}/{student}/runs/{annotator_name}/{run_id}/cards.json
  - 同时写：run_manifest.json、prompt_log.txt
  - 聚合报告：archive/{dataset_id}/reports/{annotator_name}/{run_id}/batch_annotation_report.json

  ———

  ## Phase 0（补充：你提到“最开始的音频 metadata”）

  - 把“从文件名提取的 class_code/date/progress/student/file_id + oss_url/local_path”作为 上游权威
    索引 固化在 archive/{dataset_id}/metadata.json（你给的结构）
  - 对应的代码入口建议落在 scripts/migrate_backend_input_to_archive.py（或新建 ingest 脚本），职
    责是“生成/更新 metadata + 复制/链接音频到学生目录”。

  如果你同意，我下一步就按 Phase 1 开始改代码（重点是 PromptContextBuilder.build、
  extract_timestamp_text_from_asr_json、Gemini 输出时间戳校验、FunASR sentences 校验），保证你能
  完整跑通且严格失败。