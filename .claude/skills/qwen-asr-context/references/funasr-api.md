# FunASR API 参考

DashScope 平台的 Fun-ASR 录音文件识别 API。

## 说话人分离参数

```python
from dashscope.audio.asr import Transcription

task_response = Transcription.async_call(
    model="fun-asr",               # 稳定版（当前 = fun-asr-2025-11-07）
    file_urls=[oss_url],            # HTTP(S) URL 列表，最多 100 个
    language_hints=["zh", "en"],    # 语言代码
    vocabulary_id=vocab_id,         # 热词表 ID（可选）
    diarization_enabled=True,       # 开启说话人分离
    speaker_count=2,                # 指定说话人数（2-100，可选）
)
```

**注意**：`Transcription.async_call()` 不支持本地文件，必须传 HTTP(S) URL。

## 轮询查询

```python
import time
from http import HTTPStatus

task_id = task_response.output.task_id

while True:
    resp = Transcription.fetch(task=task_id)
    if resp.output.task_status in ("SUCCEEDED", "FAILED"):
        break
    time.sleep(3)

if resp.status_code == HTTPStatus.OK:
    for item in resp.output.results:
        if item["subtask_status"] == "SUCCEEDED":
            result = requests.get(item["transcription_url"]).json()
```

## 返回格式（开启说话人分离）

```json
{
  "transcripts": [{
    "channel_id": 0,
    "text": "全文文本",
    "sentences": [
      {
        "begin_time": 2920,
        "end_time": 3840,
        "text": "island。",
        "sentence_id": 1,
        "speaker_id": 0,
        "words": [
          {"begin_time": 2920, "end_time": 3080, "text": "is"},
          {"begin_time": 3080, "end_time": 3840, "text": "land"}
        ]
      }
    ]
  }]
}
```

- `speaker_id`: 说话人索引，从 0 开始
- 时间单位：毫秒
- 热词管理：通过 `VocabularyService` 创建/复用槽位

## 已知局限

- 单声道手机录音 + 音色差异小时，说话人分离可能失败（全部归为 spk0）
- 中文准确度低于 Qwen ASR（常见错误：岛屿→导演，日出→运输）
- 英文专有名词识别较弱（Mogao Caves→more高caves）
