# Gemini API 调用方式对比报告

**测试日期**: 2025-12-29
**测试班级**: Zoe61330_2025-12-15
**测试模型**: gemini-2.5-pro
**学生数量**: 5

---

## 1. 总体对比

| 指标 | 中转站 (Relay) | 官方 SDK (Official) |
|------|---------------|---------------------|
| 成功率 | 4/5 (80%) | 4/5 (80%) |
| 平均响应时间 | **66.0s** | **54.0s** |
| 总耗时 | 264.1s | 215.9s |

---

## 2. 学生级别详细对比

| 学生 | 中转站成绩 | 中转站耗时 | 官方成绩 | 官方耗时 | 成绩差异 | 耗时差异 |
|------|-----------|-----------|---------|---------|---------|---------|
| Allen | B (2错) | 84.76s | A (0错) | 70.92s | **不一致** | +13.84s |
| Apollo | B (2错) | 69.21s | B (2错) | 55.99s | 一致 | +13.22s |
| Cici | C (7错) | 57.14s | ❌ 失败 | - | - | - |
| Feifei | B (1错) | 52.96s | A (0错) | 42.78s | **不一致** | +10.18s |
| Jessie | ❌ 失败 | - | B (1错) | 46.24s | - | - |

---

## 3. 关键发现

### 3.1 响应时间
- **官方 SDK 更快**: 平均快约 **12 秒** (22% 提升)
- 中转站增加了网络中转延迟

### 3.2 成功率
- 两者成功率相同 (80%)，但失败的学生不同
- **中转站失败**: Jessie (1 个无效 card_timestamp)
- **官方失败**: Cici (6 个无效 card_timestamp)

### 3.3 评分一致性
- 在 3 个共同成功的学生中:
  - **Apollo**: 完全一致 (B, 2错)
  - **Allen**: 不一致 (中转站 B vs 官方 A)
  - **Feifei**: 不一致 (中转站 B vs 官方 A)

> ⚠️ **注意**: 相同模型、相同输入，但评分结果存在差异。这可能是由于:
> 1. LLM 输出的随机性 (temperature=0.2)
> 2. 中转站和官方 API 的细微差异
> 3. System Instruction 处理方式不同

---

## 4. 失败原因分析

### 中转站 - Jessie 失败
```
cards 校验失败: 1 个无效项
card_index: 7, card_timestamp: None
```

### 官方 SDK - Cici 失败
```
cards 校验失败: 6 个无效项
card_index: 3, 7, 8 等 card_timestamp: None
```

---

## 5. 结论与建议

### 优势对比

| 方面 | 中转站 | 官方 SDK |
|------|-------|---------|
| 速度 | 较慢 (~66s) | **较快 (~54s)** |
| 稳定性 | 相当 | 相当 |
| 网络要求 | 需要代理 | 需要翻墙 |
| 成本 | 取决于中转站定价 | 官方定价 |

### 建议

1. **生产环境**: 如果网络条件允许，优先使用官方 SDK (速度更快)
2. **网络受限**: 中转站是可行的替代方案，功能基本一致
3. **评分差异**: 需要关注 LLM 输出的稳定性，考虑增加重试或人工复核机制

---

## 6. 原始数据

### 中转站结果
```json
[
  {"student": "Allen", "grade": "B", "errors": 2, "time_ms": 84758},
  {"student": "Apollo", "grade": "B", "errors": 2, "time_ms": 69212},
  {"student": "Cici", "grade": "C", "errors": 7, "time_ms": 57144},
  {"student": "Feifei", "grade": "B", "errors": 1, "time_ms": 52963},
  {"student": "Jessie", "grade": null, "errors": null, "time_ms": null, "status": "failed"}
]
```

### 官方 SDK 结果
```json
[
  {"student": "Allen", "grade": "A", "errors": 0, "time_ms": 70917},
  {"student": "Apollo", "grade": "B", "errors": 2, "time_ms": 55990},
  {"student": "Cici", "grade": null, "errors": null, "time_ms": null, "status": "failed"},
  {"student": "Feifei", "grade": "A", "errors": 0, "time_ms": 42777},
  {"student": "Jessie", "grade": "B", "errors": 1, "time_ms": 46243}
]
```
