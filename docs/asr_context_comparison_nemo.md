# ASR Context 对比测试报告

**测试对象**: Niko60900_2025-11-12/Nemo
**Prompt 版本**: v1.0.0 (时间戳更新)
**测试时间**: 2026-01-05T19:14:53+08:00

## 测试目标

验证 asr_context prompt 的稳定性，更新 metadata.json 时间戳后确认 ASR 输出一致。

## Prompt 内容

```markdown
这里是中英混合的文本。请准确转写音频内容，保留所有中英文。
注意，本录音场景为英语教育相关，如抽背单词等：
1. 经常会出现一些英文的词性，比如说noun和verb
2. 小孩子可能会有口齿不清的情况，请注意识别
```

## 对比结果

### 前版本 (2026-01-05T08:51:15Z)

```
Teapot, T E A P O T. Teapot.床。Bed, B E D. Bed.桌子，餐桌。Table, T A B L E. Table.台灯，桌，书桌，桌子。Desk, D E S K. Desk.椅子。Chair, C H A I R. Chair.沙发。Sofa, S O F A. Sofa.长椅，睡椅。Couch, C O U C H. Couch.帐篷。Tent, T E N T. Tent.
```

**特点**:
- ✅ 正确识别中英混合内容
- ✅ 单词拼写完整（T E A P O T 等）
- ✅ 中文释义准确

### 后版本 (2026-01-05T11:22:29Z)

```
Teapot, T E A P O T. Teapot.床。Bed, B E D. Bed.桌子，餐桌。Table, T A B L E. Table.台灯，桌，书桌，桌子。Desk, D E S K. Desk.椅子。Chair, C H A I R. Chair.沙发。Sofa, S O F A. Sofa.长椅，睡椅。Couch, C O U C H. Couch.帐篷。Tent, T E N T. Tent.
```

**特点**:
- ✅ 输出完全一致
- ✅ 中英混合识别稳定
- ✅ 无质量回归

## 技术指标对比

| 指标 | 前版本 | 后版本 | 变化 |
|------|--------|--------|------|
| input_tokens | 1115 | 1161 | +46 |
| output_tokens | 117 | 117 | 0 |
| audio_tokens | 1095 | 1095 | 0 |
| text_tokens | 20 | 66 | +46 |
| total_tokens | 1232 | 1278 | +46 |
| 音频时长 | 43s | 43s | 0 |

**说明**: text_tokens 增加 46 是因为 system context 被完整使用，符合预期。

## 识别的单词列表

| 序号 | 英文单词 | 中文释义 | 拼写 |
|------|----------|----------|------|
| 1 | Teapot | (茶壶) | T E A P O T |
| 2 | Bed | 床 | B E D |
| 3 | Table | 桌子，餐桌 | T A B L E |
| 4 | Desk | 台灯，桌，书桌，桌子 | D E S K |
| 5 | Chair | 椅子 | C H A I R |
| 6 | Sofa | 沙发 | S O F A |
| 7 | Couch | 长椅，睡椅 | C O U C H |
| 8 | Tent | 帐篷 | T E N T |

## 结论

- ✅ ASR 输出稳定，两次运行结果完全一致
- ✅ 中英混合场景识别正常
- ✅ prompt v1.0.0 工作正常，无需变更
- ✅ metadata.json 时间戳已更新

**备份文件**: `archive/Niko60900_2025-11-12/Nemo/2_qwen_asr_before_v1.0.0.json`
