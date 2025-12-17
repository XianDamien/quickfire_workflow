# Tasks: enhance-asr-questionbank-context

## 实施步骤

### 1. 前置验证 ✓
- [x] 确认题库文件存在
  - `questionbank/R1-65-D5.json` ✓
  - `questionbank/R3-14-D4.json` ✓
- [x] 确认测试音频文件存在
  - `backend_input/Zoe41900_2025-09-08_R1-65-D5_Cathy.mp3` ✓
  - `backend_input/Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3` ✓
- [x] 确认题库内容包含关键词
  - R1-65-D5.json 包含 "all" ✓
  - R3-14-D4.json 包含 "升高" ✓

### 2. 代码修改
**文件**: `scripts/qwen_asr.py`

#### 2.1 修复题库查找逻辑（第945-965行）
- [ ] 移除错误的 `progress_prefix` 逻辑
- [ ] 实现精确匹配：优先查找 `{progress}.json`
- [ ] 保留 fallback：使用 `find_questionbank_file(progress)`
- [ ] 添加详细日志输出

**修改位置**: `process_audio_file` 函数中的词汇文件查找部分

**预期代码**:
```python
# 查找词汇文件（来自 questionbank）
project_root = Path(__file__).parent.parent
vocab_file = None

questionbank_dir = project_root / "questionbank"
if questionbank_dir.exists():
    # 方案 1: 精确匹配 {progress}.json
    exact_match = questionbank_dir / f"{progress}.json"
    if exact_match.exists() and "vocabulary" not in exact_match.name.lower():
        vocab_file = str(exact_match)
        print(f"   📚 题库（精确匹配）: {exact_match.name}")
    else:
        # 方案 2: 使用通用查找函数
        fallback_file = find_questionbank_file(progress)
        if fallback_file:
            vocab_file = str(fallback_file)
            print(f"   📚 题库（模糊匹配）: {Path(vocab_file).name}")

if not vocab_file:
    print(f"   ⚠️  警告：未找到题库 (progress={progress})，ASR 将不使用上下文")
```

#### 2.2 增强日志输出
- [ ] 在转写开始前打印题库文件路径
- [ ] 打印 progress 信息以便调试
- [ ] 如果未找到题库，输出警告信息

### 3. 测试执行

#### 3.1 测试 Cathy 音频（R1-65-D5）
- [ ] 创建输出目录: `/tmp/asr_test/cathy`
- [ ] 运行 ASR:
  ```bash
  python scripts/qwen_asr.py \
      backend_input/Zoe41900_2025-09-08_R1-65-D5_Cathy.mp3 \
      --output-dir /tmp/asr_test/cathy
  ```
- [ ] 验证日志显示题库加载: `📚 题库（精确匹配）: R1-65-D5.json`
- [ ] 检查输出文件 `/tmp/asr_test/cathy/2_qwen_asr.json`
- [ ] 验证识别结果中包含 "all"（而非 "哦"）

#### 3.2 测试 Stefan 音频（R3-14-D4）
- [ ] 创建输出目录: `/tmp/asr_test/stefan`
- [ ] 运行 ASR:
  ```bash
  python scripts/qwen_asr.py \
      backend_input/Zoe51530_2025-09-08_R3-14-D4_Stefan.mp3 \
      --output-dir /tmp/asr_test/stefan
  ```
- [ ] 验证日志显示题库加载: `📚 题库（精确匹配）: R3-14-D4.json`
- [ ] 检查输出文件 `/tmp/asr_test/stefan/2_qwen_asr.json`
- [ ] 验证识别结果中包含 "升高"（而非 "身高"）

### 4. 结果分析
- [ ] 对比测试前后识别准确率
- [ ] 记录具体改善情况（哪些词汇识别正确了）
- [ ] 如果效果不佳，检查：
  - ASR 是否真正接收到上下文？
  - 上下文格式是否正确？
  - 是否需要增加更多热词？

### 5. 文档更新（如果需要）
- [ ] 更新 Serena memory 中的相关记录
- [ ] 如果发现新问题，记录到 OpenSpec proposal

## 验收标准
1. ✅ 代码修改完成，逻辑清晰
2. ✅ 两个音频测试成功运行
3. ✅ 日志显示题库正确加载
4. ✅ 识别结果明显改善或完全正确
5. ✅ 无使用 mock 数据

## 时间估算
- 代码修改: 15 分钟
- 测试执行: 20 分钟（包括 ASR API 调用时间）
- 结果分析: 10 分钟
- **总计**: ~45 分钟

## 依赖项
- `DASHSCOPE_API_KEY` 环境变量已设置
- 网络连接正常（调用阿里云 API）
- Python 3.12.12 环境

## 潜在阻塞点
1. 如果 API Key 失效或配额不足 → 无法完成测试
2. 如果题库上下文格式不符合 ASR 要求 → 需要调整 `build_context_text` 方法
3. 如果识别效果仍然不佳 → 可能需要增加更多热词或调整上下文策略
