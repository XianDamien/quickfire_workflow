# 分类器错误模式参考

迭代 prompt 时参考此文件，了解已发现的边界案例及根因。

---

## 核心判断原则

**看教学目的，不看表面形式。**

即使练习中出现大量英文单词，也要看是在教"记词义"还是在教"语法规则/构词规律"。

---

## Grammar 被误判为 Vocabulary 的典型案例

### 1. 介词固定搭配（Preposition Collocations）

**错误模式**：老师提示中文，学生说出介词短语，逐条问答，形式像词汇。

**示例文本**：
> 匆忙的什么 a hurry？In a hurry. 立刻什么 once？At once. 住院什么 hospital？In hospital. 值日什么 duty？On duty.

**为何是 grammar**：教的是固定介词搭配规则（in/on/by + 名词），而不是单词词义。

---

### 2. 代词/限定词辨析（Both / All / Neither）

**错误模式**：含大量单词选择题，看起来像词汇测试。

**示例文本**：
> 定代词快速反应。Lily, Lucy and Kate both还是all want to stay here？All。因为他们有三个人，大于了两个，要用all。

**为何是 grammar**：教的是代词选择规则（≥3人用 all，2人用 both）。

---

### 3. 后缀构词规律（Suffix Rules）

**错误模式**：逐个列出单词+中文意思，看起来像词汇。

**示例文本**：
> 说出下列名词的中文意思。worker。工人。doctor。医生。actress。女演员。importance。重要性。difference。不同点。activity。活动。movement。运动。

**为何是 grammar**：教的是后缀规律（-er/-or/-ess/-ance/-tion/-ity/-ment），词义只是辅助，核心是构词规则。

---

### 4. 动词→名词转换（Verb-to-Noun Conversion）

**错误模式**：问答格式"行为动词→名词"，像词汇对练。

**示例文本**：
> 老师说中文，你说英文。行为动词，提到。refer。名词，提及，参考。reference。行为动词，回收。recycle。名词，回收。recycling。

**为何是 grammar**：教的是动词变名词的构词规则，不是单词记忆。

---

### 5. 前缀规律（Prefix Rules: dis-/un-/im-）

**错误模式**：反义词对比练习，形式上像词汇。

**示例文本**：
> 意思有什么变化？相反的意思。like→不喜欢。appear→消失。disappear。agree→不同意。disagree。approve→disapprove。

**为何是 grammar**：教的是 dis- 前缀表"相反"的规律，核心是构词规则。

---

### 6. 词性完整转换链（Full Word-Form Chain）

**错误模式**：一个词根衍生多种词性，看起来像批量词汇。

**示例文本**：
> nation国家，它的adj全国性怎么说？national。nationality怎么说？nationality。nature自然，它的adj自然的？natural。necessary adj必要的，必要地？necessarily。必要性？necessity。

**为何是 grammar**：教的是同一词根在 noun/adj/adv 下的形态变化规律。

---

## Vocabulary 被误判为 Grammar 的案例

### 1. 含联想记忆的单词课（Mnemonic Vocabulary）

**特征**：出现"提示"二字 + 创意联想故事或谐音。

**示例文本**：
> engine，提示它本来是个音译。引擎。engineer，发动机的人。工程师。enjoy，提示印脚印，有的长辈喜欢把小孩的脚印在脸上。享受。enough，阿里巴巴的故事，一拿就富了。足够。

**识别信号**：`提示 + 联想故事` / 谐音口诀 / 脑筋急转弯式记忆。

---

---

## 标注不一致案例（历史）

| 文件 | 原标注 | 正确标注 | 内容描述 |
|------|--------|----------|---------|
| Zoe51530_2026-02-03/Leson/5 | grammar | vocabulary | dream/dress/drink 逐词词义 |
| Zoe51530_2026-02-03/Leson/6 | vocabulary | grammar | 词性转换链练习 |
