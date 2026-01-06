# Claude Code 新手入门指南

欢迎使用 Claude Code！本指南帮助你用 **Skill（技能）** 自动化日常工作，比如文案润色、文档整理、数据分类等。

---

## 🎯 基础操作速查

### 键盘快捷键
| 操作 | 快捷键 | 说明 |
|------|--------|------|
| 返回对话 | **双击 ESC** | 随时回到主对话界面 |
| 中断任务 | **单击ESC** | 停止正在执行的任务 |

### 核心命令（Slash Commands）

在输入框输入 `/` 可查看所有可用命令：

```bash
/clear      # 清除当前对话历史（释放上下文，重新开始）
/context    # 查看当前上下文使用情况
/help       # 查看帮助文档
/tasks      # 查看正在运行的任务
```

**何时使用 `/clear`？**
- 切换到完全不同的任务时（比如从文案润色切换到数据整理）
- 上下文过载导致 Claude 响应变慢时
- 需要 Claude "忘记"之前的讨论重新开始时

---

## 📂 推荐的工作目录结构

建议创建一个专门的目录来组织你的工作资料：

```
~/my-claude-workspace/           # 你的工作根目录
├── templates/                   # 模板示例文件
│   ├── email_templates/         # 邮件模板
│   ├── report_templates/        # 报告模板
│   └── social_media/            # 社交媒体文案模板
├── references/                  # 参考资料
│   ├── brand_guidelines.md      # 品牌规范
│   ├── writing_style.md         # 写作风格指南
│   └── data_standards.xlsx      # 数据标准
├── inputs/                      # 待处理的原始文件
│   └── drafts/                  # 草稿文件
├── outputs/                     # 处理完成的文件
│   └── archive/                 # 归档
└── WORKSPACE.md                 # 工作区说明文档
```

**让 Claude 帮你创建和管理：**
```
请帮我在 ~/my-claude-workspace/ 创建上述目录结构，
并生成一个 WORKSPACE.md 说明文档
```

---

## 📄 @ 符号：读取文件的魔法

使用 `@` 符号可以让 Claude 直接读取文件内容：

### 基础用法

```
@/path/to/file.md              # 读取单个文件
@templates/email_templates/    # 读取文件夹（会列出文件列表）
@references/brand_guidelines.md # 读取品牌规范
```

### 实际工作场景

**场景 1：文案润色**
```
请按照 @references/writing_style.md 的风格要求，
润色 @inputs/drafts/product_intro.md
```

**场景 2：批量处理**
```
请将 @inputs/drafts/ 中的所有文件按照
@templates/report_templates/standard.md 格式重新整理
```

**场景 3：对比学习**
```
对比 @templates/email_templates/formal.md 和 casual.md，
帮我理解正式和非正式邮件的区别
```

### 最佳实践

✅ **DO（推荐）：**
- 先 `@` 引用参考资料，再提任务
- 让 Claude 知道要遵循哪些标准和模板
- 使用 `@WORKSPACE.md` 让 Claude 了解你的工作流程

❌ **DON'T（避免）：**
- 一次引用过多文件（会占用大量上下文）
- 使用反斜杠路径 `\`（Windows 用户注意，必须用 `/`）

---

## 🛠️ Skill：你的自动化工具箱

### 什么是 Skill？

Skill 是给 Claude 的**专项能力包**，把重复的工作流程固化下来。例如：

| Skill 类型 | 用途示例 |
|-----------|---------|
| **文案润色** | 按照品牌调性自动改写营销文案 |
| **文档整理** | 将杂乱笔记按模板重新格式化 |
| **数据分类** | 根据规则自动标注 Excel 数据 |
| **内容翻译** | 遵循术语表进行专业翻译 |
| **报告生成** | 从原始数据生成标准化报告 |

### Skill 存放位置

**用户级 Skill（全局可用）：**
```
~/.claude/skills/              # 先在这里找
├── writing-polish/            # 文案润色 skill
├── doc-organizer/             # 文档整理 skill
└── data-classifier/           # 数据分类 skill
```

**如果上面没找到，会去插件目录递归查找：**
```
~/.claude/plugins/             # 递归查找所有子目录
└── custom-skills/
    └── report-generator/
```

### 调用 Skill

**方法 1：Slash Command（推荐）**
```bash
/writing-polish               # 直接调用文案润色 skill
/doc-organizer                # 调用文档整理 skill
```

**方法 2：自然语言触发**
```
帮我润色这段文案：
[粘贴你的文案]
```
（如果有匹配的 Skill，Claude 会自动识别并使用）

---

## 🔄 Skill 工作流：从需求到自动化

### 完整流程示例：创建"文案润色 Skill"

#### **步骤 1：识别重复工作**

如果你经常做这样的事：
```
请帮我改写这段营销文案：
- 语气要专业但友好
- 突出产品优势
- 控制在 200 字以内
- 避免使用"很好""非常"等模糊词

[文案内容]
```

每次都要重复这些规则 → **说明需要 Skill！**

#### **步骤 2：让 Claude A 创建 Skill**

```
我经常需要你润色营销文案，要求是：
1. 语气专业但友好
2. 突出产品价值点
3. 200 字以内
4. 避免模糊形容词

请在 ~/.claude/skills/marketing-polish/ 创建一个 Skill
```

Claude 会帮你：
- 创建目录结构
- 编写 SKILL.md（技能说明）
- 设置触发条件

#### **步骤 3：测试 Skill（开新对话 = Claude B）**

```bash
/clear                        # 清空对话，模拟全新用户
/marketing-polish             # 调用新 skill
```

然后粘贴一段测试文案，看是否按预期工作。

#### **步骤 4：迭代优化（回到 Claude A）**

如果发现问题：
```
我测试了 marketing-polish skill，发现它没有检查字数限制。
请更新 skill：
- 严格控制在 200 字
- 如果超长，优先删减形容词
```

#### **步骤 5：观察行为路径**

关注 Claude B 是否：
- ✅ 正确读取了 skill 文件
- ✅ 按预期应用了所有规则
- ❌ 忽略了某些指令（说明写得不够明确）
- ❌ 读取顺序奇怪（说明结构不直观）

---

## 📊 上下文管理：让 Claude 记住重要信息

### 查看上下文使用情况

```bash
/context
```

会显示：
- 当前已使用的 token 数
- 上下文窗口剩余空间
- 已加载的文件列表

### 上下文优化策略

**策略 1：分批处理**
```
# ❌ 不好的做法（一次加载太多）
请整理 @inputs/drafts/ 下的 50 个文件

# ✅ 好的做法（分批）
请先整理 @inputs/drafts/part1/ 的 10 个文件
（等处理完后）
现在处理 part2/ 的 10 个文件
```

**策略 2：使用 Serena MCP 存储记忆**
```
请把刚才总结的品牌规范要点存入 serena 记忆，
标题为"品牌文案规范摘要"
```

下次可以直接调用：
```
根据 serena 中的"品牌文案规范摘要"润色这段文案
```

**策略 3：归档到文档而非命令行**
```
请把整理后的内容保存到 @outputs/organized_notes.md，
不要只在命令行输出
```

---

## 🎓 新手实战演练

### 任务 1：搭建工作环境

```
请帮我创建一个工作目录 ~/writing-workspace/，包含：
- templates/ 存放邮件和报告模板
- references/ 存放写作风格指南
- inputs/ 和 outputs/ 分别存放原始和处理后的文件
- 生成 README.md 说明这个工作区的用途
```

### 任务 2：让 Claude 整理现有文件

```
我有一堆杂乱的 Markdown 笔记在 ~/Downloads/，
请帮我：
1. 按主题分类（技术/生活/工作）
2. 移动到 ~/writing-workspace/inputs/ 对应子文件夹
3. 生成一个分类清单
```

### 任务 3：体验 @ 符号

```
@~/.claude/skills/              # 列出你现有的所有 skills
@~/.claude/skills/skill-creator/SKILL.md  # 查看 skill 创建指南
```

### 任务 4：上下文管理实验

```
/context                        # 查看当前上下文
@references/long_document.pdf   # 加载一个大文件
/context                        # 对比变化
/clear                          # 清空
/context                        # 确认已清空
```

---

## ⚠️ 常见陷阱

### 1. 文件路径错误（跨平台问题）
❌ **错误：** `@templates\email.md`（Windows 反斜杠）
✅ **正确：** `@templates/email.md`（**始终用正斜杠**）

### 2. 上下文过载
**症状：** Claude 响应变慢、遗漏信息、重复提问
**解决：**
```bash
/clear                          # 清空上下文
# 然后只加载必要文件重新开始
```

### 3. Skill 未触发
**可能原因：**
- Skill 的 description 不够明确
- 触发词与实际描述不匹配
- Skill 文件放错位置

**调试方法：**
```
请列出 @~/.claude/skills/ 和 @~/.claude/plugins/
下的所有 skill 文件
```

### 4. 文件找不到
**检查顺序：**
```
1. 确认文件路径正确（绝对路径或相对路径）
2. 使用 / 而非 \
3. 检查文件是否真实存在（可让 Claude 帮忙 ls）
```

---

## 💡 高效工作流速查卡

### 开始新任务前

```
1. /clear                       # 清空无关上下文
2. @references/标准文档.md      # 加载规范/模板
3. 明确描述任务目标             # 让 Claude 理解意图
4. /context                     # 确认上下文合理
```

### 使用 Skill 处理任务

```
1. /skill-name                  # 调用对应 skill
   或者自然语言触发："请按 XX 标准润色文案"
2. 提供输入文件或内容
3. 检查输出结果
4. 如果不满意，调整输入或迭代 skill
```

### 整理和归档

```
1. 让 Claude 保存结果到 outputs/
2. 重要规律存入 serena 记忆
3. 更新模板和参考资料
4. /clear 为下次任务做准备
```

---

## 🚀 进阶技巧

### 让 Claude 帮你管理 Skill 目录

```
请检查 ~/.claude/skills/ 下的所有 skill，
按功能分类列出（文案类/数据类/文档类），
并建议哪些可以合并或优化
```

### 让 Claude 整理参考资料

```
我有很多零散的品牌规范文件在 ~/Downloads/，
请帮我：
1. 提取关键信息
2. 合并成一个标准的 brand_guidelines.md
3. 保存到 references/ 目录
```

### 批量应用 Skill

```
请对 @inputs/drafts/ 中的所有 .md 文件
应用 /writing-polish skill，
输出到 @outputs/polished/
```

---

## 📚 延伸学习

- **Skill 创建：** `@~/.claude/skills/skill-creator/SKILL.md`
- **上下文管理：** 学习使用 Serena MCP 长期记忆
- **工作流优化：** 让 Claude 帮你生成自定义 WORKSPACE.md

---

## 🆘 遇到问题时

```
1. 双击 ESC                     # 回到主界面
2. /tasks                       # 检查运行中的任务
3. Ctrl+C                       # 必要时中断
4. /clear                       # 重新开始
5. /help                        # 查阅官方帮助
```

---

**提示：** 你可以把这个指南保存到你的工作区：
```
请把这份指南保存到 ~/my-claude-workspace/QUICKSTART.md
```

**祝你工作自动化愉快！🎉**
