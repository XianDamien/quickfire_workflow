# Feature Branch 合并问题记录

日期: 2026-03-02
操作: 将 `feature/questionbank-asr-processor`（86 commits）合并到 `main`

---

## 1. 长期未合并的 Feature 分支

**现象**: feature 分支从 `449ca85` 分叉后独立开发 86 个 commit，main 也有独立提交，双线并行。

**后果**: 合并时产生 4 个冲突，且文件类型不一致（symlink vs 普通文件）。

**规范**:
- 定期（1-2 周）将 main 合并到 feature 分支，或用 `git rebase main` 保持线性
- 长期分支至少用 `git log main..feature/xxx --oneline | wc -l` 观察差异规模

## 2. CLAUDE.md 类型冲突（distinct types）

**现象**: main 上 `CLAUDE.md` 是普通文件，feature 分支是 symlink（`-> AGENTS.md`）。Git 报 `distinct types` 无法自动合并，生成 `CLAUDE.md~HEAD` 备份。

**处理**:
```bash
rm CLAUDE.md CLAUDE.md~HEAD   # 删除冲突产物
# 手动写入合并后的内容
git add CLAUDE.md
```

**教训**: 普通文件 ↔ symlink 的转换是破坏性变更，应在 commit message 中注明，并在 PR 中重点 review。

## 3. Pre-commit Hook 误拦截删除操作

**现象**: hook 用 `git diff --cached --name-only` 匹配 `data/` 目录，不区分 Add/Modify/Delete，导致删除已跟踪的数据文件也被拦截。

**根因**: `--name-only` 只输出文件名，丢失了操作类型信息。

**修复**: 改用 `--diff-filter=d`（小写 d = 排除 Delete）:
```bash
# 修复前
git diff --cached --name-only

# 修复后：只检查新增和修改，跳过删除
git diff --cached --diff-filter=d --name-only
```

**`--diff-filter` 参数说明**:
| 参数 | 含义 |
|------|------|
| `A` | 只显示 Added |
| `M` | 只显示 Modified |
| `D` | 只显示 Deleted |
| `d` | 排除 Deleted（小写 = 排除） |
| `AM` | 只显示 Added + Modified |
| `ACDMRT` | 显示所有类型 |

## 4. `git push` 无 upstream 跟踪

**现象**: `git push` 报 `no upstream branch`。

**原因**: 本地 main 的 upstream 跟踪关系丢失（可能因为 remote 重设或某些操作清除了 tracking）。

**修复**:
```bash
git push -u origin main       # 推送 + 设置跟踪
git branch -vv                 # 验证跟踪关系
```

**预防**: 用 `git branch -vv` 定期检查关键分支的跟踪状态。

## 5. `git branch -d` 报 "not fully merged"

**现象**: feature 分支已合并到 HEAD，但 `git branch -d` 仍报错。

**原因**: 合并时排除了部分文件（xlsx），导致 feature 分支的某些 commit 内容不完全存在于 HEAD。Git 对比的是 commit 内容，不是 merge 记录。

**处理**:
```bash
git branch -d <branch>   # 安全删除：要求所有 commit 内容存在于 upstream
git branch -D <branch>   # 强制删除：不检查，确认已合并时可用
```

---

## 常用 Git 命令速查

### 合并与冲突
```bash
git merge <branch>                          # 合并
git merge --abort                           # 放弃合并
git diff --cached --name-status             # 暂存区变更（含 A/D/M 状态）
git diff --cached --diff-filter=d --name-only  # 暂存区中非删除的文件
```

### 暂存区操作
```bash
git reset HEAD <file>           # 从暂存区移出（不改文件）
git rm --cached <file>          # 从 Git 跟踪移除（保留本地文件）
git restore --staged <file>     # 同 git reset HEAD（Git 2.23+ 推荐写法）
```

### 分支与远程
```bash
git branch -vv                  # 查看分支 + upstream 跟踪
git push -u origin <branch>     # 推送 + 设置 upstream
git log main..<branch> --oneline | wc -l   # 分支领先 main 多少 commit
```
