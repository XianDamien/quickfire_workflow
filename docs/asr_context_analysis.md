**根因与现象**
- `qwen_test.py` 直接把整段词汇内容（含词性+中文释义）作为 system message，几乎和音频朗读内容逐字匹配；`qwen_asr.py` 则用 `build_context_text()` 生成的 “Domain vocabulary” 列表，缺少词性提示，且将 JSON 中的 `question`(英文) 放在前、`answer`(中文) 放在括号里，和音频的朗读形式不一致，模型对“rise”名词含义的约束显著减弱，出现了“身高”这种常见同音误判。
- 词汇表加载/格式化存在预期错位：`load_vocabulary`（`scripts/qwen_asr.py:324`）把题库 list 转成 `{idx: [question, answer]}`，而 `build_context_text`（`scripts/qwen_asr.py:364`）注释里期望 `{中文, English}`，最终上下文成了 `rise(升高、升起、上涨、增长)` 这种“英文在前、中文在括号”的格式，未利用 `hint` 里的词性信息。
- API 选项不同：`qwen_test.py`（`scripts/qwen_test.py:14-23`）只设了 `enable_itn=False`，未指定语言/语言识别；`qwen_asr.py`（`scripts/qwen_asr.py:437-458`）显式设置 `language="zh"`, `enable_lid=True`，并用 `file://` 路径（`scripts/qwen_asr.py:560`），默认允许分段并发（本次文件因时长/ffprobe 判断走了单次调用路径，但参数差异仍可能影响置信度分布）。
- Stefan 的转写结果（`asr/Stefan.json`）里 “rise名词，身高。升高...” 清晰体现了 context 不足以约束第一义项；而手动 context 的 `qwen_test.py` 结果把第一义项识别为“升高”，与题库一致。

**上下文文本对比**
```
# qwen_test.py system message
Simple形容词。简单的、简易的、朴素的、简朴的。Complete形容词。完整的、完全的、彻底的。Complete及物动词。完成。... rise不及物动词。太阳、月亮等上升、上涨、起立、起床。rise名词。升高、升起、上涨、增长。raise及物动词。抬高，举起，提高，养育，提起话题。...

# qwen_asr.py build_context_text(R3-14-D4.json)
Domain vocabulary: simple(简单的、简易的、朴素的、简朴的), complete(完整的、完全的、彻底的), complete(完成), list(清单、目录、一览表), list(把什么什么列成表，举例), assist(帮助、助攻), assist(参加、出席), assist(帮助、促进), scientist(科学家), tourist(旅游者、观光者), case(箱子、盒子、情况、状况), chase(追捕、追求、雕刻、试图赢得), chase(奔跑、追赶), chase(追捕、争取、狩猎), purchase(购买), purchase(购买、购买的物品), increase(增加、增大), increase(增加、增长), rise(太阳、月亮等上升、上涨、起立、起床), rise(升高、升起、上涨、增长), raise(抬高，举起，提高，养育，提起话题), surprise(使惊奇，使诧异), surprise(惊讶，令人吃惊的是), exercise(锻炼，运动，体操，练习，习题), exercise(练习，锻炼), praise(赞扬，表扬), praise(赞扬，表扬，称赞), noise(嘈杂声，喧闹声，噪音)
```

**具体差异点（代码位）**
- 硬编码上下文：`scripts/qwen_test.py:10-12` 直接把目标文本写入 system message，与音频高度匹配。
- 词表加载与上下文构建：`scripts/qwen_asr.py:324-355` 读取题库时返回 `[question, answer]`；`scripts/qwen_asr.py:364-407` 把第一个值当“中文”、第二个当“English”，并只输出“词(释义)”列表，不含 `hint` 词性。
- 调用参数：`scripts/qwen_test.py:14-23` 仅配置 `enable_itn=False`；`scripts/qwen_asr.py:437-458` 使用 `language="zh"`, `enable_lid=True`，`file://` 路径，且支持分段并行（`scripts/qwen_asr.py:520-624`）——本次文件应走单请求，但参数仍与测试脚本不一致。
- Endpoint 设置：`qwen_test.py:4-5` 强制北京域名；`qwen_asr.py` 未覆写，走默认 base URL。

**修复/优化建议**
1) 让上下文贴合题库结构与音频朗读：在 `build_context_text` 里使用 `hint` + `question` + `answer` 生成类似 “rise名词。升高、升起、上涨、增长。” 的句式；同时统一顺序为 “英文 + 词性 + 中文释义” 或直接复用题库文本，避免当前中英文角色颠倒。  
2) 规范字段顺序：要么调整 `load_vocabulary` 输出为 `[中文, English]` 再进入现有 `build_context_text`，要么修改 `build_context_text` 把 `question` 视为英文、`answer` 视为中文，并显式加入 `hint`。  
3) 统一 API 选项：与验证脚本保持一致（例如禁用 `enable_lid` 或确认默认），并在两处都显式设定相同的 base_http_api_url / model / result_format，以减少不可控差异。  
4) 调试可视化：在调用前打印或保存最终 system context，方便核对与题库、音频的一致性，防止再出现隐性格式偏差。  
5) 如仍有个别词误判，可在 context 中单独强化易混词（如“rise 名词=升高”），或在音频前增加简短提示，引导模型优先使用题库含义。

下一步可按以上修改 `qwen_asr.py`，重新跑 Stefan 音频验证“rise”是否稳定输出“升高”。