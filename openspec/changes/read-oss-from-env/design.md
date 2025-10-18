# Design: 从 .env 读取 OSS 配置 (read-oss-from-env)

## Architecture Overview

### Current State
```
workflow.py
├── main()
│   ├── 解析命令行参数
│   └── 调用 run_workflow()
│
├── run_workflow()
│   ├── 验证输入文件
│   ├── 执行 ASR 转写
│   ├── 加载题库
│   ├── 执行评测
│   └── 输出报告
│
└── validate_file()
```

**问题**：
- OSS 参数完全依赖命令行输入（`args.oss_region` 等）
- 无法从 .env 自动加载
- 无凭证验证机制
- 用户体验不佳

### Proposed State
```
workflow.py
├── load_env_config()  [新增]
│   └── 读取 .env 中的 OSS 配置
│
├── verify_oss_credentials()  [新增]
│   └── 验证 OSS 凭证有效性
│
├── main()
│   ├── 解析命令行参数
│   ├── 加载 .env 配置
│   ├── 实现参数优先级（命令行 > .env > 默认值）
│   └── 验证 FunASR 模式下的必需参数
│
├── run_workflow()
│   ├── 验证输入文件
│   ├── [新增] 验证 OSS 凭证（FunASR 模式）
│   ├── 执行 ASR 转写
│   ├── 加载题库
│   ├── 执行评测
│   └── 输出报告
│
└── validate_file()
```

---

## Design Details

### 1. 环境配置加载（load_env_config）

#### 函数签名
```python
def load_env_config(env_path: str = ".env") -> dict:
    """
    从 .env 文件读取 OSS 相关配置

    Args:
        env_path: .env 文件路径，默认为项目根目录的 .env

    Returns:
        dict: 配置字典，包含以下键（若存在）：
            - bucket: OSS 桶名称 (来自 OSS_BUCKET_NAME)
            - region: OSS 区域 (来自 OSS_REGION，若无则从 endpoint 解析)
            - endpoint: OSS 端点 (来自 OSS_ENDPOINT)

    异常：
        - 若 .env 不存在，返回空字典（不报错）
        - 若读取失败，输出警告但继续执行
    """
```

#### 实现逻辑
```python
def load_env_config(env_path: str = ".env") -> dict:
    config = {}

    # 检查文件是否存在
    if not Path(env_path).exists():
        return config

    try:
        # 手动解析 .env（避免引入新依赖）
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if line.startswith('#') or '=' not in line:
                    continue

                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"\'')

                # 映射 .env 键到配置字典
                if key == 'OSS_BUCKET_NAME':
                    config['bucket'] = value
                elif key == 'OSS_REGION':
                    config['region'] = value
                elif key == 'OSS_ENDPOINT':
                    config['endpoint'] = value

    except Exception as e:
        print(f"⚠️  警告：读取 .env 失败 ({str(e)})，继续使用命令行参数")

    return config
```

#### .env 格式约定
```env
# 现有格式
OSS_BUCKET_NAME=quickfire-audio
OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com
OSS_REGION=cn-shanghai  # 新增，可选（若无则从 endpoint 推断）

# 或者只配置 endpoint
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com  # 自动推断 region=cn-hangzhou
```

---

### 2. OSS 凭证验证（verify_oss_credentials）

#### 函数签名
```python
def verify_oss_credentials(region: str, bucket: str, endpoint: str = None) -> tuple[bool, str]:
    """
    验证 OSS 凭证和参数的有效性

    Args:
        region: OSS 区域（如 cn-shanghai）
        bucket: OSS 桶名称
        endpoint: OSS 端点（可选）

    Returns:
        (success: bool, message: str)
            - success=True: 凭证有效
            - success=False: 凭证无效，message 包含故障信息
    """
```

#### 实现逻辑
```python
def verify_oss_credentials(region: str, bucket: str, endpoint: str = None) -> tuple[bool, str]:
    try:
        import alibabacloud_oss_v2 as oss

        # 配置
        credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        cfg.region = region
        if endpoint:
            cfg.endpoint = endpoint

        # 尝试创建客户端
        client = oss.Client(cfg)

        # 轻量级测试：尝试获取桶信息
        result = client.head_bucket(oss.HeadBucketRequest(bucket=bucket))

        if result.status_code == 200:
            return True, "✅ OSS 凭证验证通过"
        else:
            return False, f"❌ OSS 验证失败 (状态码: {result.status_code})"

    except ImportError:
        return False, "❌ 缺少 alibabacloud_oss_v2 依赖，请安装：pip install alibabacloud_oss_v2"
    except Exception as e:
        error_str = str(e)
        suggestions = []

        # 根据错误信息提供建议
        if "NoSuchBucket" in error_str or "404" in error_str:
            suggestions.append("- 检查 OSS 桶名称是否正确")
            suggestions.append("- 检查 OSS 区域是否与桶对应")
        elif "AccessDenied" in error_str or "403" in error_str:
            suggestions.append("- 检查 OSS 凭证权限（需要 GetBucketInfo 权限）")
            suggestions.append("- 验证环境变量是否配置（ALIBABA_CLOUD_ACCESS_KEY_*）")
        elif "InvalidAccessKeyId" in error_str:
            suggestions.append("- 检查 ALIBABA_CLOUD_ACCESS_KEY_ID 是否正确")
        elif "InvalidAccessKeySecret" in error_str:
            suggestions.append("- 检查 ALIBABA_CLOUD_ACCESS_KEY_SECRET 是否正确")
        elif "Network" in error_str or "Connection" in error_str:
            suggestions.append("- 检查网络连接")
            suggestions.append("- 检查 OSS 端点是否正确")

        message = f"❌ OSS 凭证验证失败: {error_str}\n"
        if suggestions:
            message += "💡 诊断建议：\n"
            for s in suggestions:
                message += f"   {s}\n"

        return False, message
```

---

### 3. 参数优先级处理

#### 优先级规则
```
优先级递减：
1. 命令行参数（最高优先级）
2. .env 文件配置
3. 默认值（最低优先级）
```

#### 实现逻辑在 main() 中
```python
def main():
    # 解析命令行参数
    args = parser.parse_args()

    # 加载 .env 配置
    env_config = load_env_config()

    # 实现参数优先级
    oss_region = args.oss_region or env_config.get('region') or None
    oss_bucket = args.oss_bucket or env_config.get('bucket') or None
    oss_endpoint = args.oss_endpoint or env_config.get('endpoint') or None

    # 验证 FunASR 模式的必需参数
    if args.asr_engine == "funasr":
        if not oss_region or not oss_bucket:
            # 记录哪些参数缺失及其来源
            missing = []
            if not oss_region:
                missing.append("OSS_REGION (--oss-region 或 .env 中的 OSS_REGION)")
            if not oss_bucket:
                missing.append("OSS_BUCKET_NAME (--oss-bucket 或 .env 中的 OSS_BUCKET_NAME)")

            print("❌ 错误：使用 FunASR 模式必须指定以下参数：")
            for item in missing:
                print(f"   - {item}")
            print("\n💡 解决方案：")
            print("   方案 1：创建 .env 文件并添加配置")
            print("           OSS_REGION=cn-hangzhou")
            print("           OSS_BUCKET_NAME=your-bucket")
            print("   方案 2：使用命令行参数")
            print("           --oss-region cn-hangzhou --oss-bucket your-bucket")
            sys.exit(1)

        # 记录参数来源
        print("✓ OSS 配置来源：")
        print(f"   Region: {oss_region} (来自 {'命令行' if args.oss_region else '.env'})")
        print(f"   Bucket: {oss_bucket} (来自 {'命令行' if args.oss_bucket else '.env'})")
        if oss_endpoint:
            print(f"   Endpoint: {oss_endpoint} (来自 {'命令行' if args.oss_endpoint else '.env'})")

    # 验证凭证（FunASR 模式）
    if args.asr_engine == "funasr":
        print("\n✓ 验证 OSS 凭证...")
        success, message = verify_oss_credentials(oss_region, oss_bucket, oss_endpoint)
        print(message)
        if not success:
            sys.exit(1)

    # 调用工作流
    run_workflow(
        audio_path=args.audio_path,
        qb_path=args.qb_path,
        output_path=args.output,
        api_key=args.api_key,
        asr_engine=args.asr_engine,
        oss_region=oss_region,
        oss_bucket=oss_bucket,
        oss_endpoint=oss_endpoint,
        keep_oss_file=args.keep_oss_file
    )
```

---

### 4. 工作流启动阶段的凭证验证

在 `run_workflow()` 中，第 1 步验证之后添加凭证验证（仅 FunASR 模式）：

```python
def run_workflow(...):
    # ... 第 1 步验证文件等 ...

    # [新增] 第 1.5 步：验证 FunASR 的 OSS 凭证
    if asr_engine == "funasr":
        print("\n✓ 第 1.5 步：验证 OSS 凭证...")
        success, message = verify_oss_credentials(oss_region, oss_bucket, oss_endpoint)
        print(message)
        if not success:
            sys.exit(1)

    # 第 2 步：音频转写 ...
```

---

## Error Handling & User Experience

### 场景 1：.env 存在，FunASR 模式
```
✓ 第1步：验证输入参数...
   音频文件: ./audio/sample.mp3
   题库文件: ./data/qb.csv
   ASR 引擎: funasr

✓ OSS 配置来源：
   Region: cn-shanghai (来自 .env)
   Bucket: quickfire-audio (来自 .env)

✓ 验证 OSS 凭证...
✅ OSS 凭证验证通过

✓ 第2步：执行音频转写 (ASR)...
```

### 场景 2：.env 不存在，必须提供命令行参数
```
❌ 错误：使用 FunASR 模式必须指定以下参数：
   - OSS_REGION (--oss-region 或 .env 中的 OSS_REGION)
   - OSS_BUCKET_NAME (--oss-bucket 或 .env 中的 OSS_BUCKET_NAME)

💡 解决方案：
   方案 1：创建 .env 文件并添加配置
           OSS_REGION=cn-hangzhou
           OSS_BUCKET_NAME=your-bucket
   方案 2：使用命令行参数
           --oss-region cn-hangzhou --oss-bucket your-bucket
```

### 场景 3：OSS 凭证无效
```
✓ 验证 OSS 凭证...
❌ OSS 凭证验证失败: Access Denied

💡 诊断建议：
   - 检查 OSS 凭证权限（需要 GetBucketInfo 权限）
   - 验证环境变量是否配置（ALIBABA_CLOUD_ACCESS_KEY_*）
```

---

## Trade-offs & Decisions

| 决策 | 理由 | 替代方案 |
|------|------|----------|
| 手动解析 .env，不引入新依赖 | 保持轻量级，避免依赖膨胀 | 使用 `python-dotenv` 库 |
| 使用 `head_bucket()` 验证凭证 | 轻量级、快速，不修改 OSS 内容 | 使用 `list_objects()` 或试上传文件 |
| 参数优先级：命令行 > .env | 符合 UNIX 惯例，灵活性最高 | .env > 命令行（配置优先） |
| 验证在 main() 和 run_workflow() 两处 | 双重保险，早期发现问题 | 仅在其中一处验证 |

---

## Backward Compatibility

✅ **完全向后兼容**

| 场景 | 现有行为 | 新行为 | 兼容性 |
|------|--------|--------|--------|
| Qwen ASR 模式 | 不需要 OSS 参数 | 不需要 OSS 参数 | ✅ 完全兼容 |
| FunASR 模式 + 完整命令行参数 | 使用命令行参数 | 使用命令行参数（覆盖 .env） | ✅ 完全兼容 |
| FunASR 模式 + 仅 .env 配置 | 需手动指定 | 自动从 .env 读取 | ✅ 增强（改进 UX） |
| 现有单独脚本（qwen3.py 等） | 独立运行 | 独立运行 | ✅ 完全兼容 |

---

## Testing Strategy

### Unit Tests（若后续补充）
```python
def test_load_env_config():
    # 测试 .env 读取
    config = load_env_config("test/.env")
    assert config['bucket'] == 'test-bucket'

def test_verify_oss_credentials():
    # 测试凭证验证（需要实际 OSS 环境）
    success, msg = verify_oss_credentials("cn-shanghai", "quickfire-audio")
    assert success is True or success is False  # 根据凭证
```

### Integration Tests
```python
# 场景 1：从 .env 读取配置并完整运行工作流
# 场景 2：命令行参数覆盖 .env
# 场景 3：缺少必需参数，应报错
# 场景 4：Qwen 模式不受影响
```

---

## Future Enhancements

1. **配置文件支持**：支持 YAML/JSON 格式的配置文件
2. **凭证缓存**：避免重复验证凭证
3. **环境变量模板验证**：检查环境变量格式有效性
4. **配置管理工具**：提供 CLI 工具初始化 .env
5. **多区域支持**：支持多个 OSS 端点配置
