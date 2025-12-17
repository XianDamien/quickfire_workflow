# Git 大文件清理指南

## 问题描述

### 遇到的错误

1. **`git pull` 失败**
   ```
   There is no tracking information for the current branch.
   ```

2. **`git push` 失败**
   ```
   fatal: The current branch feature/questionbank-asr-processor has no upstream branch.
   ```

3. **推送异常缓慢**
   ```
   Writing objects: 73% (116/158), 110.14 MiB | 8.07 MiB/s
   ```
   发现推送了 110MB+ 数据，明显不正常。

### 根本原因

1. **新分支未设置 upstream** - 本地新建的分支没有与远程建立关联
2. **大文件已提交到 Git 历史** - 在添加 `.gitignore` 之前，已经 commit 了大量大文件：
   - `归档.zip` (256 MB)
   - 多个 `.mp4` 视频文件 (6-40 MB)
   - `.zip` 压缩包 (11-15 MB)
   - **总计约 500MB+**

> `.gitignore` 只能阻止**未来**的提交，无法删除**已经**在 Git 历史中的文件。

---

## 解决方案

### 1. 检查 Git 历史中的大文件

```bash
git rev-list --objects --all | \
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
  sed -n 's/^blob //p' | \
  sort -rnk2 | head -20
```

### 2. 备份当前分支

```bash
git branch backup-before-cleanup
```

### 3. 使用 git-filter-repo 清理历史

```bash
# 安装 (如果没有)
brew install git-filter-repo

# 移除大文件和目录
git filter-repo \
  --path homework_submission/ \
  --path-glob '*.mp4' \
  --path-glob '*.zip' \
  --path-glob 'audio/*.mp3' \
  --invert-paths \
  --force
```

> `--invert-paths` 表示"移除匹配的路径"

### 4. 重新添加 remote

`git-filter-repo` 会自动移除 origin，需要重新添加：

```bash
# Fork 工作流
git remote add origin https://github.com/你的用户名/仓库名.git
git remote add upstream https://github.com/原始仓库用户名/仓库名.git
```

### 5. 强制推送

```bash
git push --set-upstream origin 分支名 --force
```

---

## 清理效果

| 指标 | 清理前 | 清理后 |
|------|--------|--------|
| 最大文件 | 256 MB | 151 KB |
| .git 目录 | ~500 MB | 548 KB |
| 推送时间 | 10+ 分钟 | 瞬间完成 |

---

## 后续理想流程

### 项目初始化时

```bash
# 1. 先创建完整的 .gitignore
# 包含所有大文件类型：*.mp4, *.zip, *.mp3, 数据目录等

# 2. 再进行第一次 commit
git add .
git commit -m "Initial commit"
```

### 日常开发流程

```bash
# 1. 新建分支
git checkout -b feature/xxx

# 2. 开发并提交
git add .
git commit -m "feat: xxx"

# 3. 首次推送时设置 upstream
git push --set-upstream origin feature/xxx

# 4. 后续推送
git push
```

### 检查清单 (每次 commit 前)

- [ ] 确认 `.gitignore` 包含所有大文件类型
- [ ] 运行 `git status` 检查是否有不该提交的大文件
- [ ] 使用 `git diff --stat` 检查文件大小是否合理

### Fork 仓库的同步流程

```bash
# 从上游同步最新代码
git fetch upstream
git checkout main
git merge upstream/main

# 推送到自己的 fork
git push origin main
```

---

## 预防措施

### 推荐的 .gitignore 配置

```gitignore
# 大文件类型
*.mp4
*.mov
*.zip
*.7z
*.rar
*.mp3
*.wav

# 数据目录
homework_submission/
archive/
audio/
backend_input/
backend_output/
```

### Git LFS (大文件存储)

如果确实需要版本控制大文件，使用 Git LFS：

```bash
# 安装
brew install git-lfs
git lfs install

# 追踪大文件类型
git lfs track "*.mp4"
git lfs track "*.zip"

# 确保 .gitattributes 被提交
git add .gitattributes
```

---

## 相关命令速查

| 操作 | 命令 |
|------|------|
| 查看大文件 | `git rev-list --objects --all \| git cat-file ... \| sort -rnk2` |
| 查看 .git 大小 | `du -sh .git` |
| 查看 remote | `git remote -v` |
| 设置 upstream | `git push --set-upstream origin 分支名` |
| 强制推送 | `git push --force` |
