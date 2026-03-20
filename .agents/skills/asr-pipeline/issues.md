# ASR Pipeline Issues

## 2026-03-20

以 `gemini-3.1-flash-lite-preview` 做金标准回归时：

- `R1/Zoe70930_2026-02-02/Candice` 可稳定跑通，且 grammar 只加载 `R1` 子集
- `R2/Zoe41900_2026-02-04/Youyou` 能跑完整条链路，但仍有 3 个待修问题

### R2/Youyou 失败明细

- `3/2_qwen_asr.json`
  Ground truth: `R072-01_介词固定搭配1.json`
  现象: 预测成 `R073-03_介词组合2.json`
  线索: `gt_search_match_count = 0`，说明正确题库在 Q/A 搜索阶段就没有被召回进候选。

- `4/2_qwen_asr.json`
  Ground truth: `R072-02_介词固定搭配2.json`
  现象: `predicted = null`
  报错: `题库候选为空`
  线索: 搜索和过滤之后没有候选留下来，需要检查该片段的 Q/A 解析结果和召回规则。

- `5/2_qwen_asr.json`
  Ground truth: `V1-17-D7.json`
  现象: `predicted = null`
  报错: `超过最大轮次 (8)`
  线索: vocabulary 候选很多，function calling 在 8 轮内没有收敛提交答案。

### 已确认有效的改动

- 目录递归规则已兼容 `two_output/<bucket>/<class>/<student>/...`
- `bucket` 可为 `R1`、`R2`、`130`
- grammar 题库索引已按 `R1/R2/R3` 懒加载，不再默认扫描完整 grammar 题库
