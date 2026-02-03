# 🚨 严重安全事件：API Key 大规模泄漏报告

**报告时间**: 2026-02-03
**项目**: quickfire_workflow
**GitHub仓库**: https://github.com/XianDamien/quickfire_workflow

---

## 📊 泄漏概览

| API类型 | 泄漏的Key | 影响文件数 | 风险等级 |
|---------|-----------|-----------|---------|
| **Google/Gemini** | `***GOOGLE_API_KEY_REDACTED***` | **17个** | 🔴 **极高** |
| **DashScope/Qwen** | `***DASHSCOPE_API_KEY_REDACTED***` | **3个** | 🔴 **极高** |

---

## 🚨 立即行动清单（按优先级）

### ⚡ Priority 1: 撤销API Keys（5分钟内完成）

#### Google/Gemini API Key
1. 访问: https://console.cloud.google.com/apis/credentials
2. 找到key: `***GOOGLE_API_KEY_REDACTED***`
3. 点击**删除**或**禁用**
4. 生成新的API key
5. 检查使用记录是否有异常调用

#### DashScope API Key
1. 访问: https://dashscope.console.aliyun.com/apiKey
2. 找到key: `***DASHSCOPE_API_KEY_REDACTED***`
3. 点击**删除**
4. 生成新的API key
5. 检查计费记录

### ⚡ Priority 2: 清理本地代码（10分钟内完成）

运行以下命令立即删除所有包含敏感信息的文件：

```bash
# 删除整个泄漏目录
rm -rf docs/comparison_test/

# 删除单个文件
rm scripts/qwen_audio.py
rm -rf openspec/changes/establish-baseline-specs/
```

### ⚡ Priority 3: 从Git历史彻底清除（30分钟内完成）

见下方详细步骤。

---

## 📁 详细泄漏文件清单

### Google/Gemini API Key 泄漏 (17个文件)

```
docs/comparison_test/QUICK_START_Zoe61330.md:28
docs/comparison_test/EXECUTION_CHECKLIST.md:13
docs/comparison_test/test_execution_script_Zoe61330.sh:9
docs/comparison_test/READY_TO_EXECUTE.md:64
docs/comparison_test/manual_commands_Zoe61330.md:8
docs/comparison_test/INDEX.md:73
docs/comparison_test/README.md:215
docs/comparison_test/TESTING_GUIDE.md:67
docs/comparison_test/Zoe41900_2025-10-24_RESULTS_TEMPLATE.md:7
docs/comparison_test/test_results_tracking_Abby61000.md:9
docs/comparison_test/MANUAL_TEST_COMMANDS.md:16
docs/comparison_test/EXECUTE_TEST.md:16
docs/comparison_test/test_tracking_Zoe61330.md:13
docs/comparison_test/TESTING_SUMMARY_Abby61000.md:71
docs/comparison_test/manual_test_commands_Abby61000.md:14
docs/comparison_test/README_Abby61000_Test.md:52
docs/comparison_test/TEST_SUMMARY_Zoe61330.md:15
```

### DashScope API Key 泄漏 (3个文件)

```
scripts/qwen_audio.py:7
openspec/changes/establish-baseline-specs/specs/workflow-orchestration/spec.md:595
```

---

## 🔧 完整补救步骤

### Step 1: 立即撤销API Keys ✅

按照上方 Priority 1 执行。

### Step 2: 备份并清理本地代码

```bash
# 1. 备份整个仓库
cd /Users/damien/Desktop/Venture
cp -r quickfire_workflow quickfire_workflow_backup_$(date +%Y%m%d_%H%M%S)

# 2. 进入工作目录
cd quickfire_workflow

# 3. 删除泄漏的文件和目录
rm -rf docs/comparison_test/
rm scripts/qwen_audio.py
rm -rf openspec/changes/establish-baseline-specs/

# 4. 确认删除
git status
```

### Step 3: 从Git历史中彻底清除

#### 方法A: 使用 git-filter-repo (推荐)

```bash
# 安装工具
brew install git-filter-repo

# 删除整个目录的历史
git filter-repo --path docs/comparison_test/ --invert-paths
git filter-repo --path scripts/qwen_audio.py --invert-paths
git filter-repo --path openspec/changes/establish-baseline-specs/ --invert-paths

# 替换所有历史中的API key
git filter-repo --replace-text <(cat <<'EOF'
***GOOGLE_API_KEY_REDACTED***==>***GOOGLE_API_KEY_REDACTED***
***DASHSCOPE_API_KEY_REDACTED***==>***DASHSCOPE_API_KEY_REDACTED***
EOF
)
```

#### 方法B: 使用 BFG Repo-Cleaner (更快，适合大仓库)

```bash
# 安装
brew install bfg

# 创建替换文件
cat > api-keys-to-remove.txt <<'EOF'
***GOOGLE_API_KEY_REDACTED***
***DASHSCOPE_API_KEY_REDACTED***
EOF

# 删除目录
bfg --delete-folders comparison_test
bfg --delete-files qwen_audio.py

# 替换API keys
bfg --replace-text api-keys-to-remove.txt

# 清理
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### Step 4: 强制推送到GitHub

```bash
# 设置代理
set_proxy

# 强制推送（⚠️ 这会重写历史）
git push origin --force --all
git push origin --force --tags
```

### Step 5: 通知GitHub清除缓存

**选项1: 联系GitHub Support**
- 访问: https://support.github.com/contact
- 说明情况：API keys泄漏，需要清除缓存的commits
- 提供commits hash

**选项2: 删除并重新创建仓库（最彻底）**
```bash
# 在GitHub上删除仓库
# 重新创建同名仓库
# 推送清理后的代码

git remote set-url origin https://github.com/XianDamien/quickfire_workflow.git
git push -u origin main --force
```

---

## 🛡️ 预防措施

### 1. 更新 .gitignore

```bash
cat >> .gitignore <<'EOF'

# ==========================================
# 敏感信息防护 (2026-02-03 added)
# ==========================================
# 环境变量文件
.env
.env.*
!.env.example
scripts/.env

# API Keys 和凭证
*.key
*.pem
*_credentials.json
*_secrets.json

# 测试文档（经常包含示例API key）
docs/comparison_test/
docs/**/test_*.md
docs/**/*_EXECUTE*.md
EOF
```

### 2. 安装 git-secrets

```bash
# 安装
brew install git-secrets

# 初始化
cd /Users/damien/Desktop/Venture/quickfire_workflow
git secrets --install
git secrets --register-aws

# 添加自定义规则
git secrets --add 'AIza[a-zA-Z0-9_-]{35}'
git secrets --add 'sk-[a-zA-Z0-9]{32}'
git secrets --add 'GEMINI_API_KEY\s*=\s*["\'][^"\']+["\']'
git secrets --add 'DASHSCOPE_API_KEY\s*=\s*["\'][^"\']+["\']'

# 扫描历史
git secrets --scan-history
```

### 3. 配置 pre-commit hook

```bash
# 创建 hook
cat > .git/hooks/pre-commit <<'HOOK'
#!/bin/bash

echo "🔍 Scanning for API keys..."

# 检测Google API key
if git diff --cached | grep -E "AIza[a-zA-Z0-9_-]{35}"; then
    echo "❌ ERROR: Google API key detected!"
    exit 1
fi

# 检测DashScope key
if git diff --cached | grep -E "sk-[a-zA-Z0-9]{32}"; then
    echo "❌ ERROR: DashScope API key detected!"
    exit 1
fi

# 检测环境变量赋值
if git diff --cached | grep -E "(GEMINI_API_KEY|DASHSCOPE_API_KEY)\s*=\s*[\"'][^\"']+[\"']"; then
    echo "❌ ERROR: Hardcoded API key assignment detected!"
    exit 1
fi

echo "✅ No API keys found"
exit 0
HOOK

chmod +x .git/hooks/pre-commit

# 测试
.git/hooks/pre-commit
```

### 4. 创建 .env.example 模板

```bash
cat > .env.example <<'EOF'
# Google/Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# DashScope API Configuration
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# Instructions:
# 1. Copy this file to .env
# 2. Replace placeholder values with actual API keys
# 3. NEVER commit .env file to git
EOF
```

### 5. 代码审查清单

创建 `CODE_REVIEW_CHECKLIST.md`:

```markdown
## 提交前检查清单

- [ ] 没有硬编码的API keys
- [ ] 所有API keys从环境变量读取
- [ ] .env文件在.gitignore中
- [ ] 没有在文档中写入真实API key
- [ ] pre-commit hook正常运行
- [ ] 运行了 `git secrets --scan`
```

---

## 📈 影响评估

### 暴露时间线

```bash
# 查看文件首次提交时间
git log --all --full-history --diff-filter=A -- \
  docs/comparison_test/ \
  scripts/qwen_audio.py \
  | grep -E "(^commit|^Date:)"
```

### 潜在风险

1. **未授权API调用**
   - Google Gemini API可能被用于生成内容
   - DashScope可能被用于ASR转写

2. **费用风险**
   - 检查账单是否有异常支出
   - 设置API配额限制

3. **数据泄漏**
   - 检查API调用日志
   - 确认是否有敏感数据被处理

---

## ✅ 验证清单

完成后逐项勾选：

- [ ] **已撤销Google API key** (AIzaSyDvz...)
- [ ] **已撤销DashScope API key** (sk-44eab6e5...)
- [ ] **已生成新的Google API key**
- [ ] **已生成新的DashScope API key**
- [ ] **已更新本地 .env 文件**
- [ ] **已删除所有泄漏文件**
- [ ] **已从git历史删除敏感信息**
- [ ] **已强制推送到GitHub**
- [ ] **已配置 .gitignore**
- [ ] **已安装 git-secrets**
- [ ] **已配置 pre-commit hook**
- [ ] **已创建 .env.example**
- [ ] **已检查API使用记录**
- [ ] **已设置API用量告警**
- [ ] **已通知团队成员**

---

## 📞 后续监控

### Google Cloud Console
1. 检查API使用量: https://console.cloud.google.com/apis/dashboard
2. 设置配额告警
3. 启用API访问日志
4. 限制API key的HTTP referer

### 阿里云DashScope
1. 检查调用记录: https://dashscope.console.aliyun.com/overview
2. 查看账单明细
3. 设置每日调用上限
4. 启用异常告警

---

## 📚 参考资料

- [GitHub: Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [git-filter-repo documentation](https://github.com/newren/git-filter-repo)
- [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)
- [git-secrets](https://github.com/awslabs/git-secrets)
