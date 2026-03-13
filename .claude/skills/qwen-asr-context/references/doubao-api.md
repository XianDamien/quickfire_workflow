# 豆包 Volcengine BigASR API 参考

火山引擎大模型语音识别 API。与 DashScope 不同，状态码在 **response headers** 中返回。

## 完整调用示例

参考来源：`auc_websocket_demo.py`

### 提交任务

```python
import json, uuid, requests

submit_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/submit"

request_id = str(uuid.uuid4())

headers = {
    "X-Api-App-Key": app_key,          # 控制台 App ID
    "X-Api-Access-Key": access_key,    # 控制台 Access Token
    "X-Api-Resource-Id": "volc.bigasr.auc",
    "X-Api-Request-Id": request_id,
    "X-Api-Sequence": "-1",            # 必需
}

payload = {
    "user": {"uid": "quickfire"},
    "audio": {
        "url": oss_url,                # 必须是公开可访问的 URL
        "format": "mp3",
    },
    "request": {
        "model_name": "bigmodel",
        "enable_speaker_info": True,   # 说话人聚类
        "enable_punc": True,
        "enable_itn": True,
        "show_utterances": True,
        "corpus": {
            "context": "上下文描述文本",  # 类似 Qwen 的 system context
        },
    },
}

# 注意：用 data=json.dumps() 不是 json=
resp = requests.post(submit_url, data=json.dumps(payload), headers=headers, timeout=30)

# 状态码在 headers 里，不在 body 里！
status_code = resp.headers.get("X-Api-Status-Code", "")
x_tt_logid = resp.headers.get("X-Tt-Logid", "")  # 查询时需传回
```

### 轮询查询

```python
query_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/query"

query_headers = {
    "X-Api-App-Key": app_key,
    "X-Api-Access-Key": access_key,
    "X-Api-Resource-Id": "volc.bigasr.auc",
    "X-Api-Request-Id": request_id,
    "X-Tt-Logid": x_tt_logid,         # 从 submit 响应获取
}

while True:
    resp = requests.post(query_url, data=json.dumps({}), headers=query_headers, timeout=30)
    code = resp.headers.get("X-Api-Status-Code", "")

    if code == "20000000":    # 完成
        result = resp.json()
        break
    elif code in ("20000001", "20000002"):  # 处理中 / 排队中
        time.sleep(1)
    else:                     # 失败
        msg = resp.headers.get("X-Api-Message", "")
        raise RuntimeError(f"豆包 ASR 失败: code={code} msg={msg}")
```

### 状态码

| 码 | 含义 |
|----|------|
| 20000000 | 成功 |
| 20000001 | 处理中 |
| 20000002 | 排队中 |
| 45000001 | 参数错误 |
| 55000001 | 服务端处理错误 |

## 返回格式

```json
{
  "result": {
    "text": "全文文本",
    "utterances": [
      {
        "start_time": 2730,
        "end_time": 61350,
        "text": "Island We can go to...",
        "additions": {
          "speaker": "1"
        },
        "words": [
          {"text": "Island", "start_time": 2730, "end_time": 3200, "confidence": 0}
        ]
      }
    ]
  }
}
```

- 说话人标识在 `utterances[].additions.speaker`（字符串）
- 时间单位：毫秒
- `corpus.context` 支持最多 800 token / 20 轮

## 关键踩坑点

1. **Endpoint**：用 `openspeech-direct.zijieapi.com`，不是 `openspeech.bytedance.com`
2. **Body 序列化**：`data=json.dumps(payload)` 不是 `json=payload`
3. **状态码位置**：在 response headers `X-Api-Status-Code`，body 可能是 `{}`
4. **X-Tt-Logid**：submit 返回的 logid 必须在 query 时原样传回
5. **OSS URL**：需要 HTTPS 签名 URL，HTTP 可能报 `55000001` 处理错误
