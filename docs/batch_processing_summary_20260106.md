# 批量处理汇总报告
生成时间: 2026-01-06

## 整体概览

| 批次ID | 班级名称 | 学生数 | 成功数 | 失败数 | 总耗时 | 状态 |
|--------|---------|--------|--------|--------|--------|------|
| b969420 | Zoe41900_2025-10-24 | 4 | 4 | 0 | 8分3秒 | 完成 |
| bb115d2 | Zoe41900_2025-11-20 | 4 | 4 | 0 | 7分44秒 | 完成 |
| b4c3aef | Abby61000_2025-11-05 | 3 | 3 | 0 | 9分31秒 | 完成 |

**总计**: 11名学生，11个成功，0个失败，总耗时约25分18秒

---

## 详细数据

### 1. Zoe41900_2025-10-24 (蔬菜词汇测试)

**基本信息**:
- 任务ID: b969420
- 学生数: 4人
- 测试内容: 7个蔬菜单词 (Vegetable, Potato, Tomato, Carrot, Bean, Pea, Peanut)
- 提交时间: 2026-01-06 00:34:39
- 完成时间: 2026-01-06 00:42:42
- **总耗时**: 8分3秒

**成绩统计**:
| 学生 | 成绩 | 错误数 | 正确率 | 备注 |
|------|------|--------|--------|------|
| Lucy | A | 0 | 100% | 完美完成，"番茄"使用了同义词"西红柿" |
| Oscar | A | 0 | 100% | 完美完成 |
| Rico | B | 1 | 85.7% | "Potato"未回答 |
| You | B | 1 | 85.7% | "Peanut"语义错误（说成"坚果"） |

**成绩分布**: A级 2人 (50%), B级 2人 (50%)

---

### 2. Zoe41900_2025-11-20 (场所词汇测试)

**基本信息**:
- 任务ID: bb115d2
- 学生数: 4人
- 测试内容: 7个场所单词 (place, room, bedroom, kitchen, bathroom, supermarket, school)
- 提交时间: 2026-01-06 00:34:43
- 完成时间: 2026-01-06 00:42:27
- **总耗时**: 7分44秒

**成绩统计**:
| 学生 | 成绩 | 错误数 | 正确率 | 备注 |
|------|------|--------|--------|------|
| AL | A | 0 | 100% | 完美完成 |
| ANNA | A | 0 | 100% | 完美完成 |
| Kevin | A | 0 | 100% | 完美完成 |
| sophia | A | 0 | 100% | 完美完成 |

**成绩分布**: A级 4人 (100%)

---

### 3. Abby61000_2025-11-05 (人物词汇测试)

**基本信息**:
- 任务ID: b4c3aef
- 学生数: 3人
- 测试内容: 8个人物单词 (kid, pupil, baby, twin×2, leader, friend, classmate)
- 提交时间: 2026-01-06 00:34:47
- 完成时间: 2026-01-06 00:44:18
- **总耗时**: 9分31秒

**成绩统计**:
| 学生 | 成绩 | 错误数 | 正确率 | 备注 |
|------|------|--------|--------|------|
| Benjamin | A | 0 | 100% | 完美完成，回答全部正确 |
| Dana | B | 1 | 87.5% | "friend"未回答 |
| Jeffery | B | 2 | 75% | "twin(孪生的)"和"classmate"未回答 |

**成绩分布**: A级 1人 (33.3%), B级 2人 (66.7%)

---

## JSON格式汇总

```json
{
  "report_generated_at": "2026-01-06",
  "summary": {
    "total_batches": 3,
    "total_students": 11,
    "total_success": 11,
    "total_failures": 0,
    "total_duration_seconds": 1518,
    "total_duration_formatted": "25分18秒"
  },
  "batches": [
    {
      "task_id": "b969420",
      "batch_name": "Zoe41900_2025-10-24",
      "topic": "蔬菜词汇",
      "student_count": 4,
      "success_count": 4,
      "fail_count": 0,
      "submitted_at": "2026-01-06T00:34:39.696331",
      "completed_at": "2026-01-06T00:42:42.566165",
      "duration_seconds": 483,
      "duration_formatted": "8分3秒",
      "students": [
        {
          "name": "Lucy",
          "grade": "A",
          "errors": 0,
          "accuracy": "100%",
          "total_questions": 7,
          "notes": "完美完成，番茄使用同义词西红柿"
        },
        {
          "name": "Oscar",
          "grade": "A",
          "errors": 0,
          "accuracy": "100%",
          "total_questions": 7,
          "notes": "完美完成"
        },
        {
          "name": "Rico",
          "grade": "B",
          "errors": 1,
          "accuracy": "85.7%",
          "total_questions": 7,
          "notes": "Potato未回答"
        },
        {
          "name": "You",
          "grade": "B",
          "errors": 1,
          "accuracy": "85.7%",
          "total_questions": 7,
          "notes": "Peanut语义错误（说成坚果）"
        }
      ],
      "grade_distribution": {
        "A": 2,
        "B": 2,
        "C": 0
      }
    },
    {
      "task_id": "bb115d2",
      "batch_name": "Zoe41900_2025-11-20",
      "topic": "场所词汇",
      "student_count": 4,
      "success_count": 4,
      "fail_count": 0,
      "submitted_at": "2026-01-06T00:34:43.612034",
      "completed_at": "2026-01-06T00:42:27.559813",
      "duration_seconds": 464,
      "duration_formatted": "7分44秒",
      "students": [
        {
          "name": "AL",
          "grade": "A",
          "errors": 0,
          "accuracy": "100%",
          "total_questions": 7,
          "notes": "完美完成"
        },
        {
          "name": "ANNA",
          "grade": "A",
          "errors": 0,
          "accuracy": "100%",
          "total_questions": 7,
          "notes": "完美完成"
        },
        {
          "name": "Kevin",
          "grade": "A",
          "errors": 0,
          "accuracy": "100%",
          "total_questions": 7,
          "notes": "完美完成"
        },
        {
          "name": "sophia",
          "grade": "A",
          "errors": 0,
          "accuracy": "100%",
          "total_questions": 7,
          "notes": "完美完成"
        }
      ],
      "grade_distribution": {
        "A": 4,
        "B": 0,
        "C": 0
      }
    },
    {
      "task_id": "b4c3aef",
      "batch_name": "Abby61000_2025-11-05",
      "topic": "人物词汇",
      "student_count": 3,
      "success_count": 3,
      "fail_count": 0,
      "submitted_at": "2026-01-06T00:34:47.354083",
      "completed_at": "2026-01-06T00:44:18.020950",
      "duration_seconds": 571,
      "duration_formatted": "9分31秒",
      "students": [
        {
          "name": "Benjamin",
          "grade": "A",
          "errors": 0,
          "accuracy": "100%",
          "total_questions": 8,
          "notes": "完美完成"
        },
        {
          "name": "Dana",
          "grade": "B",
          "errors": 1,
          "accuracy": "87.5%",
          "total_questions": 8,
          "notes": "friend未回答"
        },
        {
          "name": "Jeffery",
          "grade": "B",
          "errors": 2,
          "accuracy": "75%",
          "total_questions": 8,
          "notes": "twin(孪生的)和classmate未回答"
        }
      ],
      "grade_distribution": {
        "A": 1,
        "B": 2,
        "C": 0
      }
    }
  ],
  "overall_grade_distribution": {
    "A": 7,
    "B": 4,
    "C": 0,
    "A_percentage": "63.6%",
    "B_percentage": "36.4%",
    "C_percentage": "0%"
  },
  "processing_info": {
    "model": "gemini-3-pro-preview",
    "git_commit": "eb2892635730f7403bd49dba7f064419d2056e05",
    "run_id_prefix": "20260106_003436_eb28926",
    "api_method": "batch_api"
  }
}
```

---

## 关键发现

1. **成功率**: 所有批次100%成功完成，无失败案例
2. **平均耗时**: 每个批次平均处理时间约8分26秒
3. **整体表现**:
   - A级学生: 7人 (63.6%)
   - B级学生: 4人 (36.4%)
   - C级学生: 0人 (0%)
4. **最佳表现**: Zoe41900_2025-11-20班级全员A级
5. **主要错误类型**:
   - 未回答 (NO_ANSWER): 最常见
   - 语义错误 (MEANING_ERROR): 较少

## 技术信息

- **模型**: gemini-3-pro-preview
- **Git Commit**: eb28926
- **处理方式**: Batch API
- **数据存储**: /Users/damien/Desktop/Venture/quickfire_workflow/archive/
