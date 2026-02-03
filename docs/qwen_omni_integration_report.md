# Qwen3-Omni Annotator 集成完成报告

## 实施日期
2026-02-03

## 实施内容

### 1. 核心实现

#### 新建文件
- **`scripts/annotators/qwen_omni.py`** (677 行)
  - 实现 `Qwen3OmniAnnotator` 类
  - 音频通过 base64 编码传递
  - 使用 OpenAI 兼容接口（阿里云 DashScope）
  - 支持流式响应处理
  - 完整的音频文件验证（大小 ≤100MB，时长 ≤20分钟）
  - 复用现有 prompt 模板
  - 完整的错误处理和输出保存

#### 关键特性
1. **音频验证**:
   - 文件大小检查（使用 `stat`）
   - 音频时长检查（使用 `ffprobe`）

2. **Base64 编码**:
   - 支持多种音频格式（MP3, WAV, M4A, FLAC, AAC, AMR, 3GP）
   - 自动识别 MIME 类型

3. **API 调用**:
   - 流式响应处理
   - Token 使用统计
   - 响应时间计量

4. **输出格式**:
   - 与 Gemini 完全一致的输出结构
   - 元数据扩展（音频编码时间、文件大小等）
   - Prompt log 完整记录

### 2. 配置更新

#### `scripts/annotators/config.py`
```python
# 新增模型列表
AVAILABLE_QWEN_OMNI_MODELS = ["qwen-omni-flash"]

# 新增 token 限制
MODEL_MAX_OUTPUT_TOKENS = {
    # ...
    "qwen-omni-flash": 8192,
    "qwen-omni": 8192,
    # ...
}

# 新增文件限制配置
QWEN_OMNI_LIMITS = {
    "qwen-omni-flash": {
        "max_file_size_mb": 100,
        "max_duration_minutes": 20,
    }
}
```

#### `scripts/annotators/__init__.py`
- 添加 Qwen3-Omni 路由逻辑（检测 "omni" 关键词）
- 更新 `list_annotators()` 返回列表
- 更新模块文档字符串

### 3. 文档更新

#### `CLAUDE.md`
**重写"模型规范"部分**（第 3-32 行）:
- 强调 Annotator 接口的可替换性
- 添加支持的 Annotator 对比表格
- 明确默认模型和切换方法
- 更新目录结构说明

#### `README.md`
**更新"支持的模型"部分**（第 184-190 行）:
- 添加 Qwen3-Omni 行
- 增加"输入方式"列
- 标注默认模型

#### `.env.example`
- 已包含 `DASHSCOPE_API_KEY`（无需修改）

### 4. 测试文件

#### `test_qwen_omni.py`
- 完整的测试脚本
- 使用现有测试数据（Zoe61330_2025-12-30/Cici）
- 详细的输出显示
- 错误处理和追踪

### 5. 依赖管理

#### `pyproject.toml`
```bash
# 自动添加
openai>=1.0.0
jiter==0.13.0 (依赖)
tqdm==4.67.2 (依赖)
```

## 使用方法

### 基础用法
```bash
# 使用 Qwen3-Omni Flash
python scripts/main.py \
  --archive-batch Batch123 \
  --annotator qwen-omni-flash

# 测试单个学生
python scripts/main.py \
  --archive-batch Batch123 \
  --student StudentName \
  --annotator qwen-omni-flash
```

### 编程用法
```python
from scripts.annotators import get_annotator
from scripts.common.runs import new_run_id, ensure_run_dir

# 获取 annotator
annotator = get_annotator("qwen-omni-flash")

# 创建 run 目录
run_id = new_run_id()
run_dir = ensure_run_dir(BATCH, STUDENT, annotator.name, run_id)

# 执行标注
result = annotator.run_archive_student(
    archive_batch=BATCH,
    student_name=STUDENT,
    run_dir=run_dir,
    verbose=True
)

# 检查结果
if result.success:
    print(f"评分: {result.final_grade}")
    print(f"Token: {result.response_time_ms}ms")
```

### 运行测试
```bash
# 基础测试
python test_qwen_omni.py

# 使用 uv
uv run python test_qwen_omni.py
```

## 技术规格

### API 配置
- **Base URL**: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- **认证**: `DASHSCOPE_API_KEY` 环境变量
- **接口**: OpenAI Chat Completions API
- **模式**: 流式响应 (`stream=True`)
- **输出格式**: JSON Object (`response_format: json_object`)

### 限制
| 限制项 | Flash 模型 |
|--------|-----------|
| 文件大小 | ≤ 100MB |
| 音频时长 | ≤ 20 分钟 |
| Max Output Tokens | 8192 |
| 支持格式 | MP3, WAV, M4A, FLAC, AAC, AMR, 3GP |

### 性能指标
输出元数据包含：
- `response_time_ms`: API 响应时间
- `audio_encode_time_seconds`: Base64 编码时间
- `audio_file_size_bytes`: 音频文件大小
- `audio_duration_seconds`: 音频时长
- `total_time_seconds`: 总处理时间
- `token_usage`: Token 使用统计

## 输出结构

### 文件清单
```
archive/<batch>/<student>/runs/qwen-omni-flash/<run-id>/
├── 4_llm_annotation.json    # 主输出（与 Gemini 格式一致）
├── prompt_log.txt            # 完整 prompt 记录
└── run_manifest.json         # 运行元数据
```

### `4_llm_annotation.json` 结构
```json
{
  "student_name": "StudentName",
  "validation": {
    "status": "PASS",
    "errors": []
  },
  "final_grade_suggestion": "A",
  "mistake_count": {...},
  "annotations": [...],
  "_metadata": {
    "model": "qwen-omni-flash",
    "mode": "sync_streaming",
    "response_time_ms": 5432.1,
    "token_usage": {
      "prompt_tokens": 12345,
      "completion_tokens": 2345,
      "total_tokens": 14690
    },
    "audio_encode_time_seconds": 1.25,
    "audio_file_size_bytes": 5242880,
    "audio_duration_seconds": 180.5,
    "total_time_seconds": 6.68,
    "prompt_version": "v2.0.0",
    "run_id": "20260203-123456",
    "git_commit": "abc123...",
    "timestamp": "2026-02-03T12:34:56.789"
  }
}
```

## 验证清单

### 实现完整性
- [x] `qwen_omni.py` 核心实现完成
- [x] `config.py` 配置更新完成
- [x] `__init__.py` 路由逻辑完成
- [x] `CLAUDE.md` 文档更新完成
- [x] `README.md` 文档更新完成
- [x] `test_qwen_omni.py` 测试文件创建完成
- [x] `openai` 依赖安装完成

### 代码质量
- [x] 完整的类型注解
- [x] 详细的文档字符串
- [x] 错误处理覆盖全面
- [x] 日志输出清晰
- [x] 与现有代码风格一致

### 接口一致性
- [x] 继承 `BaseAnnotator`
- [x] 实现 `annotate()` 方法
- [x] 实现 `run_archive_student()` 方法
- [x] 返回 `AnnotatorOutput` 对象
- [x] 输出文件格式与 Gemini 一致

### 功能完整性
- [x] 音频文件验证（大小+时长）
- [x] Base64 编码
- [x] MIME 类型识别
- [x] API 流式调用
- [x] Token 使用统计
- [x] Validation 逻辑
- [x] Cards 校验
- [x] 输出文件保存
- [x] Prompt log 保存
- [x] Run manifest 保存

## 待测试项

### 基础功能测试
- [ ] 音频文件大小校验（应拒绝 >100MB）
- [ ] 音频时长校验（应拒绝 >20分钟）
- [ ] Base64 编码正确性
- [ ] API 流式响应处理
- [ ] Token 使用统计正确

### 业务逻辑测试
- [ ] Validation 逻辑正常
- [ ] Cards 校验通过
- [ ] 评分结果准确
- [ ] 输出文件格式一致
- [ ] Prompt log 完整

### 集成测试
- [ ] 通过 `main.py` 调用
- [ ] 与 Gemini 结果对比
- [ ] 批量处理测试
- [ ] 错误恢复测试

### 边界测试
- [ ] DASHSCOPE_API_KEY 未设置
- [ ] API rate limit 处理
- [ ] 流式响应中断
- [ ] JSON 解析失败
- [ ] Cards 校验失败

## 建议测试命令

### 1. 单元测试
```bash
# 测试基础功能
uv run python test_qwen_omni.py
```

### 2. 集成测试
```bash
# 完整流程测试
uv run python scripts/main.py \
  --archive-batch Zoe61330_2025-12-30 \
  --student Cici \
  --annotator qwen-omni-flash

# 与 Gemini 结果对比
uv run python scripts/main.py \
  --archive-batch Zoe61330_2025-12-30 \
  --student Cici \
  --annotator gemini-3-pro-preview
```

### 3. 边界测试
```bash
# 测试大文件（应失败）
# 需要准备一个 >100MB 的音频文件

# 测试长音频（应失败）
# 需要准备一个 >20分钟的音频文件

# 测试 API key 缺失
unset DASHSCOPE_API_KEY
uv run python test_qwen_omni.py
```

## 关键文件清单

### 创建的文件
1. `scripts/annotators/qwen_omni.py` (677 行)
2. `test_qwen_omni.py` (91 行)

### 修改的文件
1. `scripts/annotators/config.py` (+11 行)
2. `scripts/annotators/__init__.py` (+11 行)
3. `CLAUDE.md` (+29 行, -11 行)
4. `README.md` (+3 行, -2 行)
5. `pyproject.toml` (uv 自动管理)

## 成功标准

### 必须满足
- [x] 代码编译无错误
- [x] 所有配置更新完成
- [x] 文档更新完整
- [x] 测试文件可执行

### 待验证
- [ ] `--annotator qwen-omni-flash` 可正常工作
- [ ] 输出格式与 Gemini 一致
- [ ] 测试用例全部通过
- [ ] 无新增安全风险（API key 泄露等）

## 下一步

1. **运行测试**: 执行 `test_qwen_omni.py` 验证基础功能
2. **集成测试**: 通过 `main.py` 测试完整流程
3. **对比验证**: 与 Gemini 结果对比，确保输出质量
4. **边界测试**: 测试各种异常情况的处理
5. **性能测试**: 评估编码时间、API 响应时间等指标
6. **文档完善**: 根据测试结果补充文档

## 注意事项

### 环境变量
确保 `.env` 文件中已配置：
```bash
DASHSCOPE_API_KEY=your_api_key_here
```

### 依赖检查
如果遇到导入错误，确认依赖已安装：
```bash
uv sync
```

### ffprobe 依赖
音频时长检查需要 `ffprobe`（ffmpeg 套件）:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg
```

如果 `ffprobe` 不可用，代码会自动跳过时长检查（只检查文件大小）。

## 兼容性

### Python 版本
- 需要 Python 3.8+

### 操作系统
- macOS ✅
- Linux ✅
- Windows ✅ (需要安装 ffmpeg)

### API 版本
- OpenAI SDK: >=1.0.0
- DashScope API: Compatible Mode v1

## 总结

本次实施完成了 Qwen3-Omni Flash 作为备用 annotator 的完整集成：

1. **核心功能**: 完整实现音频标注流程
2. **配置管理**: 统一的配置和路由系统
3. **文档完善**: 清晰的使用说明和架构说明
4. **测试支持**: 提供测试脚本和验证清单

**角色定位**: 作为可选备用方案，保持 `gemini-3-pro-preview` 为默认模型。

**关键优势**:
- 接口统一，即插即用
- 输出格式一致
- 完整的错误处理
- 详细的元数据记录

**使用建议**:
- 生产环境继续使用 Gemini 3 Pro Preview
- 测试或备用场景可使用 Qwen3-Omni Flash
- 注意文件大小和时长限制

---

**实施状态**: ✅ 代码实现完成，待功能测试验证
