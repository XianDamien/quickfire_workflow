⏺ 响应时间测试与报告生成流程总结

  1. 运行测试

  单个学生测试:
  GEMINI_API_KEY=xxx .venv/bin/python3 scripts/main.py \
    --archive-batch Zoe41900_2025-09-08 \
    --student Oscar \
    --only cards \
    --force \
    --annotator gemini-3-pro-preview

  整个数据集测试:
  GEMINI_API_KEY=xxx .venv/bin/python3 scripts/main.py \
    --archive-batch Zoe41900_2025-09-08 \
    --only cards \
    --force \
    --annotator gemini-2.5-pro

  完整流程 (含 ASR):
  # 用 --target cards 而非 --only cards
  GEMINI_API_KEY=xxx .venv/bin/python3 scripts/main.py \
    --archive-batch Zoe41900_2025-09-08 \
    --target cards \
    --force \
    --annotator gemini-2.5-pro

  2. 响应时间存储位置

  archive/{dataset}/{student}/runs/{model}/{run_id}/4_llm_annotation.json

  JSON 结构:
  {
    "_metadata": {
      "model": "gemini-3-pro-preview",
      "response_time_ms": 45160.123,
      "prompt_version": "1.1.0",
      "run_id": "20251219_083914_c51dc38",
      "timestamp": "2025-12-19T08:39:55"
    }
  }

  3. 生成报告的关键代码

  import json
  from pathlib import Path
  from collections import defaultdict

  archive_dir = Path("archive")
  results = defaultdict(lambda: defaultdict(dict))

  for dataset in ["Zoe41900_2025-09-08", "Zoe51530_2025-09-08"]:
      for student_dir in (archive_dir / dataset).iterdir():
          if not student_dir.is_dir():
              continue
          for annotator_dir in (student_dir / "runs").iterdir():
              run_dirs = sorted(annotator_dir.iterdir(), reverse=True)
              for run_dir in run_dirs[:1]:  # 最新的 run
                  f = run_dir / "4_llm_annotation.json"
                  if f.exists():
                      data = json.load(open(f))
                      time_ms = data.get("_metadata",
  {}).get("response_time_ms")
                      if time_ms:

  results[dataset][student_dir.name][annotator_dir.name] = time_ms / 1000

  4. 关键参数说明

  | 参数              | 说明                                          |
  |-----------------|---------------------------------------------|
  | --archive-batch | 数据集名称                                       |
  | --student       | 指定学生（模糊匹配）
  |
  | --only cards    | 只跑 annotation 阶段（需 ASR 已存在）
  |
  | --target cards  | 跑完整流程到 annotation                           |
  | --force         | 强制重新处理                                      |
  | --annotator     | 模型名称 (gemini-2.5-pro, gemini-3-pro-preview) |