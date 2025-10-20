# Gemini Batch Test - Quick Start Guide

## 📌 What Was Done

Modified `test_gemini_batch.py` to test Gemini 2.0 Flash with Qwen ASR data from `archive/Zoe41900-9.8/`

### Key Changes
1. **Removed src dependency** → Used direct `google.generativeai` import
2. **Fixed vocabulary loading** → Now handles JSON despite .csv extension
3. **Added audio support** → MP3 files attached to Gemini requests
4. **Proper prompt building** → Combines template + vocabulary + ASR data
5. **Rate limiting** → 2-second delays between API calls

---

## 🚀 Quick Start

### 1. Setup
```bash
# Install package
pip install google-generativeai

# Set API key
export GEMINI_API_KEY="AIzaSyBZ_CMDgUIcmtj8it3BBmdxvJTePFtLbeQ"
```

### 2. Run Test
```bash
# Simple
python3 test_gemini_batch.py

# With logging
python3 test_gemini_batch.py 2>&1 | tee test_run.log

# Background
nohup python3 test_gemini_batch.py > test_run.log 2>&1 &
```

### 3. Check Results
```bash
# View summary
cat test_outputs_v1/test_summary_v1.json

# Check one student
python3 -m json.tool test_outputs_v1/Yoyo_v1_result.json

# List all results
ls -lh test_outputs_v1/
```

---

## 📊 Test Results Summary

| Student | Grade | Hard Errors | Soft Errors | Status |
|---------|-------|-------------|-------------|--------|
| Cathy | C | 3 | 0 | ✅ |
| Frances Wang | C | 3 | 0 | ✅ |
| Lucy | C | 3 | 0 | ✅ |
| Oscar | - | - | - | ⏭️ (no ASR) |
| Rico | C | 4 | 1 | ✅ |
| Yoyo | B | 1 | 0 | ✅ |

**Summary:** 5/6 evaluated, 100% success, all v1 compliant

---

## 📁 Output Structure

```
test_outputs_v1/
├── Cathy_v1_result.json              # Individual evaluation
├── Frances_Wang_v1_result.json
├── Lucy_v1_result.json
├── Rico_v1_result.json
├── Yoyo_v1_result.json
└── test_summary_v1.json              # Batch summary
```

### Result Format (v1)
```json
{
  "final_grade_suggestion": "A|B|C",
  "mistake_count": {
    "hard_errors": 3,      // MEANING_ERROR count
    "soft_errors": 0       // PRONUNCIATION_ERROR, etc.
  },
  "annotations": [
    {
      "card_index": 0,
      "question": "不",
      "expected_answer": "not",
      "related_student_utterance": {
        "detected_text": "not",
        "start_time": 5920,
        "end_time": 7160,
        "issue_type": null  // or ERROR_TYPE
      }
    }
    // ... 10 items total
  ]
}
```

---

## 🔍 Debugging & Comparison

### View Specific Student
```bash
# Pretty print Yoyo's evaluation
python3 -c "
import json
with open('test_outputs_v1/Yoyo_v1_result.json') as f:
    data = json.load(f)
    print(f'Grade: {data[\"final_grade_suggestion\"]}')
    print(f'Hard: {data[\"mistake_count\"][\"hard_errors\"]}')
    print(f'Soft: {data[\"mistake_count\"][\"soft_errors\"]}')
    for ann in data['annotations']:
        issue = ann['related_student_utterance']
        if issue and issue['issue_type']:
            print(f\"  [{ann['card_index']}] {ann['question']} → {issue['issue_type']}\")
"
```

### Compare Error Patterns
```bash
# Extract all MEANING_ERROR items
python3 -c "
import json
import glob
for f in glob.glob('test_outputs_v1/*_v1_result.json'):
    with open(f) as fp:
        data = json.load(fp)
    student = f.split('/')[-1].split('_')[0]
    errors = [a for a in data['annotations'] if a['related_student_utterance'] and a['related_student_utterance']['issue_type'] == 'MEANING_ERROR']
    print(f'{student}: {len(errors)} MEANING_ERRORs')
"
```

### Get Grade Summary
```bash
# Show all grades
python3 -c "
import json
with open('test_outputs_v1/test_summary_v1.json') as f:
    data = json.load(f)
for r in data['results']:
    if r['status'] == 'success':
        print(f\"{r['student']:15} {r['grade']} ({r['hard_errors']} hard, {r['soft_errors']} soft)\")
    else:
        print(f\"{r['student']:15} SKIP ({r['error']})\")
"
```

---

## 🎯 Key Evaluation Metrics

### Scoring Rules (from v1)
- **A Grade:** 0 MEANING_ERROR
- **B Grade:** 1-2 MEANING_ERROR
- **C Grade:** 3+ MEANING_ERROR

### Error Types
- **MEANING_ERROR** (hard): Wrong word/meaning
- **PRONUNCIATION_ERROR** (soft): Correct meaning, wrong pronunciation
- **UNCLEAR_PRONUNCIATION** (soft): Too quiet/mumbled
- **SLOW_RESPONSE** (soft): Answered after teacher gave answer

---

## 🔧 Customization

### Change Model
```python
# In process_student(), line ~186
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",  # Change this
    system_instruction="..."
)
```

### Change Students
```python
# At top of script, line ~32
STUDENTS = ['Cathy', 'Frances Wang', 'Lucy', 'Oscar', 'Rico', 'Yoyo']
```

### Change Question Bank
```python
# At top of script, line ~38
QB_PATH = SHARED_CONTEXT_DIR / 'R1-42.csv'  # Change this
```

### Adjust Rate Limiting
```python
# In process_student(), line ~221
time.sleep(1)  # Reduce from 2 to 1 second
```

---

## 🐛 Troubleshooting

### No API Key
```
Error: GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set
→ Fix: export GEMINI_API_KEY="your-key"
```

### Missing ASR Files
```
⏭️ Oscar: No ASR file found
→ Look for: archive/Zoe41900-9.8/Oscar/2_*.json
→ Alternative: 5_qwen_asr_output.json (different pattern)
```

### Module Not Found
```
Error: No module named 'google.generativeai'
→ Fix: pip install google-generativeai
```

### JSON Parsing Error
```
Error: JSON parse error
→ Check: Response is valid JSON from Gemini
→ Verify: API returns application/json MIME type
```

---

## 📖 Related Files

- **Test Script:** `test_gemini_batch.py`
- **Report:** `TEST_GEMINI_BATCH_REPORT.md`
- **Prompt Template:** `prompts/evaluation_v1.txt`
- **QB Data:** `archive/Zoe41900-9.8/_shared_context/R1-65.csv`
- **ASR Data:** `archive/Zoe41900-9.8/*/2_intermediate_asr_raw.json`
- **Audio Files:** `archive/Zoe41900-9.8/*/1_input_audio.mp3`

---

## 📞 Next Steps

1. **For Debugging:**
   - Compare individual results between students
   - Manually verify 2-3 annotations against audio
   - Check error patterns across different QBs

2. **For Production:**
   - Test with other datasets (Zoe70930, Zoe51530, etc.)
   - Compare Gemini results vs Qwen results
   - Implement parallel processing for speed

3. **For Improvement:**
   - Add alternative ASR file detection
   - Implement result caching
   - Generate HTML/PDF reports

---

**Status:** ✅ Ready for debugging and comparison
**Last Updated:** 2025-10-20 19:26:08 UTC
**Model:** Gemini 2.0 Flash
**Output Format:** v1 (Verified ✅)
