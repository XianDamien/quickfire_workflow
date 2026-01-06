# Tasks: Remove Default Hotword Injection

**Change ID**: remove-hotword-default

---

## Phase 1: Code Changes (No Archive Modification)

### Task 1.1: Update `QwenASRProvider.transcribe_audio()`
**Dependencies**: None
**Deliverable**: Hotword injection removed from ASR API calls

**Steps**:
1. Open `scripts/asr/qwen.py`
2. Locate `transcribe_audio()` method (~line 527-585)
3. Remove vocabulary loading logic:
   ```python
   # DELETE these lines:
   if not system_context and vocabulary_path and os.path.exists(vocabulary_path):
       vocab = self.load_vocabulary(vocabulary_path)
       system_context = self.build_context_text(vocab)
   ```
4. Replace with comment:
   ```python
   # Hotword context is disabled by default to preserve mixed-language output.
   # Callers can still pass system_context_override explicitly if needed.
   system_context = system_context_override or ""
   ```
5. Update docstring to mention "default: no hotword injection"

**Validation**:
- [ ] Method signature unchanged
- [ ] `system_context_override` parameter still works if passed explicitly
- [ ] No vocabulary file is read by default

---

### Task 1.2: Update `transcribe_and_save()`
**Dependencies**: Task 1.1
**Deliverable**: Hotword building removed, always passes `None` to `transcribe_audio()`

**Steps**:
1. Locate `transcribe_and_save()` method (~line 587-643)
2. Remove hotword building logic:
   ```python
   # DELETE these lines:
   if vocabulary_path and os.path.exists(vocabulary_path):
       try:
           vocab = self.load_vocabulary(vocabulary_path)
           context_words = self.build_context_words(vocab)
       except Exception:
           context_words = []
   ```
3. Keep `context_words: List[str] = []` initialization (always empty)
4. Change `transcribe_audio()` call to pass `system_context_override=None`:
   ```python
   response = self.transcribe_audio(
       audio_path=input_audio_path,
       vocabulary_path=vocabulary_path,
       language=language,
       enable_itn=False,
       system_context_override=None,  # Changed from ", ".join(context_words) if context_words else None
   )
   ```

**Validation**:
- [ ] `context_words` always `[]`
- [ ] `transcribe_audio()` always receives `None` for system context
- [ ] Method still accepts `vocabulary_path` (for future use)

---

### Task 1.3: Update `transcribe_and_save_with_segmentation()`
**Dependencies**: Task 1.2
**Deliverable**: Parallel processing with no hotwords

**Steps**:
1. Locate `transcribe_and_save_with_segmentation()` (~line 645-789)
2. Remove hotword building logic (~line 659-665):
   ```python
   # DELETE these lines:
   if vocabulary_path and os.path.exists(vocabulary_path):
       try:
           vocab = self.load_vocabulary(vocabulary_path)
           context_words = self.build_context_words(vocab)
       except Exception:
           context_words = []
   ```
3. Keep `context_words: List[str] = []` initialization (always empty)
4. Update the `transcribe_audio()` call in thread pool (~line 740-747):
   ```python
   future = executor.submit(
       self.transcribe_audio,
       audio_path=audio_url,
       vocabulary_path=vocabulary_path,
       language=language,
       enable_itn=False,
       system_context_override=None,  # Changed from ", ".join(context_words) if context_words else None
   )
   ```
5. Verify `_save_hotwords()` is called (~line 699-704) - this should remain, will save empty lists

**Validation**:
- [ ] `context_words` always `[]`
- [ ] Parallel transcription still works
- [ ] `_save_hotwords()` called with empty list
- [ ] `2_qwen_asr_hotwords.json` generated with `"hotwords": []`

---

### Task 1.4: Update Class and Method Docstrings
**Dependencies**: Tasks 1.1-1.3
**Deliverable**: Documentation reflects new behavior

**Steps**:
1. Update class docstring (~line 277):
   ```python
   """Qwen3-ASR provider for audio transcription with custom vocabulary.

   提供 Qwen3-ASR 语音转写功能，支持：
   - 自定义词汇表/热词上下文优化识别（默认不注入）  # Updated
   - 长音频自动分段并行处理
   - 多种输入格式（本地文件、URL）
   ```
2. Update `transcribe_audio()` docstring (~line 527):
   ```python
   """
   Transcribe audio file using Qwen3-ASR.

   Note: Hotword injection is disabled by default. Pass system_context_override
   explicitly if you need custom context.

   Args:
       audio_path: Path or URL to audio file
       vocabulary_path: Reserved for future use (not used by default)
       ...
   ```

**Validation**:
- [ ] Docstrings accurately describe current behavior
- [ ] Chinese comments updated where relevant

---

## Phase 2: Archive Cleanup and Regeneration

### Task 2.1: Backup Current Archive State
**Dependencies**: None (can run in parallel with Phase 1)
**Deliverable**: Safety backup before destructive operations

**Steps**:
1. Create backup metadata:
   ```bash
   find archive -name "2_qwen_asr*.json" > /tmp/qwen_files_before_cleanup.txt
   wc -l /tmp/qwen_files_before_cleanup.txt  # Should be 139+
   ```
2. Optional: Create archive snapshot if disk space allows:
   ```bash
   tar -czf archive_backup_$(date +%Y%m%d_%H%M%S).tar.gz archive/
   ```

**Validation**:
- [ ] File list saved
- [ ] Count verified (139+ files)

---

### Task 2.2: Delete All Qwen ASR Artifacts
**Dependencies**: Task 2.1, Phase 1 complete
**Deliverable**: Clean slate for regeneration

**Steps**:
1. Delete all Qwen ASR output files:
   ```bash
   find archive -name "2_qwen_asr.json" -delete
   find archive -name "2_qwen_asr_hotwords.json" -delete
   find archive -name "2_qwen_asr_no_hotwords.json" -delete
   ```
2. Verify deletion:
   ```bash
   find archive -name "2_qwen_asr*.json" | wc -l  # Should be 0
   ```
3. Check that other files remain intact:
   ```bash
   find archive -name "1_input_audio.*" | wc -l  # Should be >0
   find archive -name "3_asr_timestamp.json" | wc -l  # Should be >0
   find archive -name "4_llm_annotation.json" | wc -l  # Should be >0
   ```

**Validation**:
- [ ] All `2_qwen_asr*.json` files deleted
- [ ] Input audio files intact
- [ ] Timestamp files intact
- [ ] Annotation files intact

---

### Task 2.3: Identify Batches for Regeneration
**Dependencies**: Task 2.2
**Deliverable**: List of all batches to process

**Steps**:
1. List all batch directories:
   ```bash
   ls -1 archive/ | grep -E "^[A-Z].*_2025-" | sort
   ```
2. Save to file:
   ```bash
   ls -1 archive/ | grep -E "^[A-Z].*_2025-" | sort > /tmp/batches_to_regenerate.txt
   ```
3. Count batches:
   ```bash
   wc -l /tmp/batches_to_regenerate.txt
   ```

**Validation**:
- [ ] Batch list saved
- [ ] Count verified (should match directory count)

---

### Task 2.4: Regenerate Qwen ASR for All Batches
**Dependencies**: Task 2.3
**Deliverable**: Fresh ASR transcriptions without hotwords

**Steps**:
1. Create regeneration script:
   ```bash
   cat > /tmp/regenerate_all.sh <<'EOF'
   #!/bin/bash
   set -e
   while read batch; do
     echo "==== Processing $batch ===="
     python3 scripts/main.py --archive-batch "$batch" --only qwen_asr --force
     echo ""
   done < /tmp/batches_to_regenerate.txt
   EOF
   chmod +x /tmp/regenerate_all.sh
   ```
2. Run regeneration (estimate: 5-10 min per batch, ~2 hours total):
   ```bash
   /tmp/regenerate_all.sh 2>&1 | tee /tmp/regeneration.log
   ```
3. Monitor progress:
   ```bash
   tail -f /tmp/regeneration.log
   ```

**Validation**:
- [ ] All batches processed without errors
- [ ] Each student has new `2_qwen_asr.json`
- [ ] Each student has new `2_qwen_asr_hotwords.json` with empty lists
- [ ] No forced language switching in spot-checked transcriptions

---

### Task 2.5: Spot-Check Transcription Quality
**Dependencies**: Task 2.4
**Deliverable**: Verified quality improvement

**Steps**:
1. Select 5 random students across different batches:
   ```bash
   find archive -name "2_qwen_asr.json" | shuf | head -5
   ```
2. For each file:
   - Open `2_qwen_asr.json`
   - Extract transcribed text: `jq -r '.output.choices[0].message.content[0].text' <file>`
   - Check for mixed-language preservation (no forced Chinese for English words)
   - Compare with `1_input_audio.*` if needed (listen to verify)
3. Check hotword metadata:
   ```bash
   jq '.hotwords | length' archive/<batch>/<student>/2_qwen_asr_hotwords.json
   # Should output: 0
   ```

**Validation**:
- [ ] 5 transcriptions checked
- [ ] No forced language switching observed
- [ ] Mixed Chinese-English preserved correctly
- [ ] All hotword files show `"count": 0`

---

## Phase 3: Documentation and Finalization

### Task 3.1: Update `scripts/README.md`
**Dependencies**: Phase 1 complete
**Deliverable**: README reflects new behavior

**Steps**:
1. Open `scripts/README.md`
2. Find section on Qwen ASR (if exists)
3. Add/update note:
   ```markdown
   ### Qwen ASR Behavior

   - **Hotword Injection**: Disabled by default (as of 2026-01-05)
   - **Rationale**: Preserves mixed-language (Chinese-English) output quality
   - **Hotword Files**: `2_qwen_asr_hotwords.json` still generated but contains empty lists
   - **Future**: Can re-enable via `system_context_override` parameter if needed
   ```

**Validation**:
- [ ] README updated
- [ ] Clear explanation of change

---

### Task 3.2: Git Commit with Clear Rationale
**Dependencies**: All tasks complete
**Deliverable**: Atomic commit documenting change

**Steps**:
1. Stage changes:
   ```bash
   git add scripts/asr/qwen.py
   git add scripts/README.md
   git add openspec/changes/remove-hotword-default/
   ```
2. Create commit:
   ```bash
   git commit -m "$(cat <<'EOF'
   feat(qwen-asr): 默认禁用热词注入以保留混合语言输出

   ## 变更内容

   1. **移除默认热词注入** (scripts/asr/qwen.py)
      - transcribe_audio() 不再自动加载词汇表
      - transcribe_and_save() 不再构建热词列表
      - transcribe_and_save_with_segmentation() 不再构建热词列表
      - 保留 _save_hotwords() 但始终保存空列表

   2. **保留代码以备未来使用**
      - load_vocabulary() 保留
      - build_context_words() 保留
      - 可通过 system_context_override 显式传入热词

   3. **清理 Archive 数据**
      - 删除所有 2_qwen_asr*.json (139 文件)
      - 使用新脚本重新生成所有批次
      - 验证混合语言输出质量改善

   ## 动机

   热词注入导致强制语言切换问题：
   - 输入: "I like apples" (英语)
   - 旧行为: "我喜欢苹果" (被强制翻译为中文)
   - 新行为: "I like apples" (保留原始语言)

   ## 验证

   ✅ 139+ ASR 文件重新生成
   ✅ 5 个样本检查确认混合语言保留
   ✅ 热词元数据文件显示空列表
   ✅ 完整 pipeline 端到端测试通过

   🤖 Generated with Claude Code

   Co-Authored-By: Claude <noreply@anthropic.com>
   EOF
   )"
   ```

**Validation**:
- [ ] Commit created
- [ ] Message clearly explains rationale
- [ ] All modified files included

---

### Task 3.3: Validation - Full Pipeline Test
**Dependencies**: All tasks complete
**Deliverable**: End-to-end verification

**Steps**:
1. Select one test batch:
   ```bash
   TEST_BATCH="Zoe41900_2025-09-08"  # Or any other batch
   ```
2. Run full pipeline:
   ```bash
   python3 scripts/main.py --archive-batch "$TEST_BATCH" --student Oscar --force
   ```
3. Verify:
   - ASR stage completes without errors
   - Timestamp stage works (if applicable)
   - Annotation stage produces valid JSON
   - No language-forcing issues in transcriptions

**Validation**:
- [ ] Full pipeline runs without errors
- [ ] ASR output has correct format
- [ ] Downstream stages (timestamps, annotation) still work
- [ ] No regression in overall system behavior

---

## Summary

**Total Tasks**: 13
**Phases**: 3

**Critical Path**:
1. Code Changes (1.1 → 1.2 → 1.3 → 1.4)
2. Archive Cleanup (2.1 → 2.2 → 2.3 → 2.4 → 2.5)
3. Documentation (3.1 → 3.2 → 3.3)

**Estimated Time**:
- Phase 1: 30 minutes
- Phase 2: 2-3 hours (mainly regeneration time)
- Phase 3: 30 minutes
- **Total**: ~3-4 hours

**Risks**:
- Archive regeneration may take longer if batches are large
- Spot-checking may reveal quality issues requiring investigation
- Pipeline dependencies may break (mitigated by end-to-end test)
