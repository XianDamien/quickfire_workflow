 已记录：旧脚本迁入 scripts/_legacy/，并且 PR-D 需要做。下面是按你要求更新后的最
  终 TODO 文档内容（可直接保存）。

  ———

  # TODO（快速版）：只保留 archive 工作流；旧脚本迁入 scripts/_legacy/；执行 PR-D

  ## 总原则

  - 只保留 archive 工作流：archive/{batch}/{student}/...
  - ASR 分工为两类能力（未来可替换实现）：
      - asr_text（纯文本、追求精确）= 当前 Qwen
      - asr_timestamp（带时间戳、sentences）= 当前 FunASR
  - 题库解析唯一入口：scripts/common/archive.py:resolve_question_bank()
  - 旧脚本只做历史备份：迁入 scripts/_legacy/，不保证可运行

  ———

  ## PR-A：冻结 archive 产物契约 + 题库解析收口 common

  目标

  - archive 产物固定：
      - 2_qwen_asr.json：Text ASR 产物（可被下游按既有路径读取 text）
      - 3_asr_timestamp.json：Timestamp ASR 产物（必须包含
        transcripts[].sentences[] 且 begin_time/end_time=int(ms)；sentences 不能
        为空）
  - 移除/停用脚本内题库解析重复实现：不再允许三份 find_archive_vocabulary_file 类
    逻辑存在于主路径

  验收 / 测试

  - 静态扫描：主路径不再有独立 archive 题库查找实现（允许极短 wrapper，但内部必须
    只调用 common）。
  - 一致性：同一个 archive_batch 在所有调用点解析到同一题库路径（至少抽 1 个 batch
    对比）。
  - python3 scripts/main.py --help 可用。

  ———

  ## PR-B：main 直连 providers（完成 archive“主流程复刻”）

  目标

  - scripts/main.py 的 DAG 不再 subprocess 调旧脚本，改为直接调用：
      - Text provider（Qwen）写 2_qwen_asr.json
      - Timestamp provider（FunASR）写 3_asr_timestamp.json
  - main 层强约束：
      - timestamps 阶段只能走 Timestamp provider（当前仅 funasr）
      - text 阶段只能走 Text provider（当前仅 qwen）

  验收 / 测试（dry-run 必须不触发网络/不写文件）

  - python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --student Oscar
    --target timestamps --dry-run --force
      - 输出必须打印：音频路径、题库路径、将写入的输出路径、将使用的 provider（且
        不出现 subprocess 命令行）
  - python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --student Oscar
    --target cards --dry-run --force

  验收 / 测试（可联网+有 key 时的 smoke）

  - 跑 1 个学生到 timestamps，生成 3_asr_timestamp.json
  - 立即用 scripts/contracts/asr_timestamp.py:extract_timestamp_text(strict=True)
    解析通过
  - 2_qwen_asr.json 的 text 读取路径保持不变（下游仍能取到 text）

  ———

  ## PR-C：旧脚本整体迁入 scripts/_legacy/（一次性清理）

  目标

  - 将以下文件移动到 scripts/_legacy/：
      - scripts/qwen_asr.py
      - scripts/funasr.py
      - scripts/Gemini_annotation.py
  - 文档入口统一指向：python3 scripts/main.py --archive-batch ...

  验收 / 测试

  - 全 repo 主路径不再 import/引用上述三个脚本（rg 全量确认）。
  - python3 scripts/main.py --help 与 PR-B 的 dry-run 命令继续通过。
  - 明确声明：scripts/_legacy/ 下内容仅备份，不做兼容保障。

  ———

  ## PR-D：移除非 archive 逻辑（更激进，只保留 archive 分支）

  目标

  - 删除/移除所有非 archive 模式分支与文档，包括但不限于：
      - backend_input 模式（单文件/批量）
      - dataset/legacy 模式
      - URL 模式（如 funasr url list）
  - 主入口只保留 archive 参数集（--archive-
    batch/--student/--target/--only/--until/--force/--dry-run 等）

  验收 / 测试

  - python3 scripts/main.py --help 中不再出现非 archive 的说明/参数。
  - 全 repo rg 确认不再存在 backend_input/dataset/url 模式路由代码（或至少主路径已
    彻底无入口）。
  - 最小回归（dry-run）：
      - python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --student
        Oscar --target timestamps --dry-run --force
      - python3 scripts/main.py --archive-batch Zoe41900_2025-09-08 --student
        Oscar --target cards --dry-run --force
  - 可联网时 smoke：选 1 个学生跑到 timestamps，timestamp 合约解析通过。

  ———