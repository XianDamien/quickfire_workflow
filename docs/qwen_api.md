---
title: "产品简介"
source: "https://help.aliyun.com/zh/model-studio/qwen-api-via-dashscope?spm=a2c4g.11186623.0.0.462a3011O06iwV"
author:
  - "[[阿里云计算]]"
published:
created: 2026-02-17
description: "阿里云百炼是一站式大模型开发与应用平台，集成了千问及主流第三方模型。它为开发者提供了兼容OpenAI的API及全链路模型服务；同时，也提供可视化应用构建能力，让业务人员能快速创建智能体、知识库问答等AI应用。"
tags:
  - "clippings"
---
[官方文档](https://help.aliyun.com/)

[用户指南（模型）](https://help.aliyun.com/zh/model-studio/what-is-model-studio) [用户指南（应用）](https://help.aliyun.com/zh/model-studio/build-knowledge-base-qa-assistant-without-coding/) [API参考（模型）](https://help.aliyun.com/zh/model-studio/get-api-key) [API参考（应用）](https://help.aliyun.com/zh/model-studio/obtain-the-app-id-and-workspace-id)

大模型服务平台百炼

[用户指南（模型）](https://help.aliyun.com/zh/model-studio/what-is-model-studio) [用户指南（应用）](https://help.aliyun.com/zh/model-studio/build-knowledge-base-qa-assistant-without-coding/) [API参考（模型）](https://help.aliyun.com/zh/model-studio/get-api-key) [API参考（应用）](https://help.aliyun.com/zh/model-studio/obtain-the-app-id-and-workspace-id)

本文介绍如何通过 DashScope API 调用千问模型，包括输入输出参数说明及调用示例。

华北2（北京）地域

新加坡地域

美国（弗吉尼亚）地域

金融云

HTTP 请求地址：

- 纯文本模型（如qwen-plus）： `POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation`
- 多模态模型（如qwen3.5-plus或qwen3-vl-plus） `POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`

SDK 调用无需配置 `base_url` 。

HTTP 请求地址：

- 纯文本模型（如qwen-plus）： `POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation`
- 多模态模型（如qwen3.5-plus或qwen3-vl-plus） `POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`

SDK调用配置的 `base_url` ：

Python代码

Java代码

```python
dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
```

- **方式一：**
	```java
	import com.alibaba.dashscope.protocol.Protocol;
	Generation gen = new Generation(Protocol.HTTP.getValue(), "https://dashscope-intl.aliyuncs.com/api/v1");
	```
- **方式二：**
	```java
	import com.alibaba.dashscope.utils.Constants;
	Constants.baseHttpApiUrl="https://dashscope-intl.aliyuncs.com/api/v1";
	```

HTTP 请求地址：

- 纯文本模型： `POST https://dashscope-us.aliyuncs.com/api/v1/services/aigc/text-generation/generation`
- 千问VL模型： `POST https://dashscope-us.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`

SDK调用配置的 `base_url` ：

Python代码

Java代码

```python
dashscope.base_http_api_url = 'https://dashscope-us.aliyuncs.com/api/v1'
```

- **方式一：**
	```java
	import com.alibaba.dashscope.protocol.Protocol;
	Generation gen = new Generation(Protocol.HTTP.getValue(), "https://dashscope-us.aliyuncs.com/api/v1");
	```
- **方式二：**
	```java
	import com.alibaba.dashscope.utils.Constants;
	Constants.baseHttpApiUrl="https://dashscope-us.aliyuncs.com/api/v1";
	```

HTTP 请求地址：

- 纯文本模型： `POST https://dashscope-finance.aliyuncs.com/api/v1/services/aigc/text-generation/generation`
- 千问VL模型： `POST https://dashscope-finance.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`

SDK调用配置的 `base_url` ：

Python代码

Java代码

```python
dashscope.base_http_api_url = 'https://dashscope-finance.aliyuncs.com/api/v1'
```

- **方式一：**
	```java
	import com.alibaba.dashscope.protocol.Protocol;
	Generation gen = new Generation(Protocol.HTTP.getValue(), "https://dashscope-finance.aliyuncs.com/api/v1");
	```
- **方式二：**
	```java
	import com.alibaba.dashscope.utils.Constants;
	public class Main {
	    static {
	        Constants.baseHttpApiUrl="https://dashscope-finance.aliyuncs.com/api/v1";
	    }
	}
	```

> 您需要已 [获取API Key](https://help.aliyun.com/zh/model-studio/get-api-key) 并 [配置API Key到环境变量](https://help.aliyun.com/zh/model-studio/configure-api-key-through-environment-variables) 。如果通过DashScope SDK进行调用，需要 [安装DashScope SDK](https://help.aliyun.com/zh/model-studio/install-sdk#f3e80b21069aa) 。

<table><tbody><tr><td rowspan="1" colspan="1"><h2>请求体</h2></td><td rowspan="29" colspan="1"><p>文本输入</p><p>流式输出</p><p>图像输入</p><p>视频输入</p><p>音频输入</p><p>联网搜索</p><p>工具调用</p><p>异步调用</p><p>文档理解</p><p>Python</p><p>Java</p><p>PHP（HTTP）</p><p>Node.js（HTTP）</p><p>C#（HTTP）</p><p>Go（HTTP）</p><p>curl</p><div><pre><code>import os
import dashscope

messages = [
    {'role': 'system', 'content': 'You are a helpful assistant.'},
    {'role': 'user', 'content': '你是谁？'}
]
response = dashscope.Generation.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    model="qwen-plus", # 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    messages=messages,
    result_format='message'
    )
print(response)</code></pre></div><div><pre><code>// 建议dashscope SDK的版本 &gt;= 2.12.0
import java.util.Arrays;
import java.lang.System;
import com.alibaba.dashscope.aigc.generation.Generation;
import com.alibaba.dashscope.aigc.generation.GenerationParam;
import com.alibaba.dashscope.aigc.generation.GenerationResult;
import com.alibaba.dashscope.common.Message;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.utils.JsonUtils;

public class Main {
    public static GenerationResult callWithMessage() throws ApiException, NoApiKeyException, InputRequiredException {
        Generation gen = new Generation();
        Message systemMsg = Message.builder()
                .role(Role.SYSTEM.getValue())
                .content("You are a helpful assistant.")
                .build();
        Message userMsg = Message.builder()
                .role(Role.USER.getValue())
                .content("你是谁？")
                .build();
        GenerationParam param = GenerationParam.builder()
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                // 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
                .model("qwen-plus")
                .messages(Arrays.asList(systemMsg, userMsg))
                .resultFormat(GenerationParam.ResultFormat.MESSAGE)
                .build();
        return gen.call(param);
    }
    public static void main(String[] args) {
        try {
            GenerationResult result = callWithMessage();
            System.out.println(JsonUtils.toJson(result));
        } catch (ApiException | NoApiKeyException | InputRequiredException e) {
            // 使用日志框架记录异常信息
            System.err.println("An error occurred while calling the generation service: " + e.getMessage());
        }
        System.exit(0);
    }
}</code></pre></div><div><pre><code>&lt;?php

$url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation";
$apiKey = getenv('DASHSCOPE_API_KEY');

$data = [
    // 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    "model" =&gt; "qwen-plus",
    "input" =&gt; [
        "messages" =&gt; [
            [
                "role" =&gt; "system",
                "content" =&gt; "You are a helpful assistant."
            ],
            [
                "role" =&gt; "user",
                "content" =&gt; "你是谁？"
            ]
        ]
    ],
    "parameters" =&gt; [
        "result_format" =&gt; "message"
    ]
];

$jsonData = json_encode($data);

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, $jsonData);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    "Authorization: Bearer $apiKey",
    "Content-Type: application/json"
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

if ($httpCode == 200) {
    echo "Response: " . $response;
} else {
    echo "Error: " . $httpCode . " - " . $response;
}

curl_close($ch);
?&gt;</code></pre></div><p>DashScope 未提供 Node.js 环境的 SDK。如需通过 OpenAI Node.js SDK调用，请参考本文的 <a href="https://help.aliyun.com/zh/model-studio/qwen-api-reference/#4ec3e641c294d">OpenAI</a> 章节。</p><div><pre><code>using System.Net.Http.Headers;
using System.Text;

class Program
{
    private static readonly HttpClient httpClient = new HttpClient();

    static async Task Main(string[] args)
    {
        // 若没有配置环境变量，请用百炼API Key将下行替换为：string? apiKey = "sk-xxx";
        string? apiKey = Environment.GetEnvironmentVariable("DASHSCOPE_API_KEY");

        if (string.IsNullOrEmpty(apiKey))
        {
            Console.WriteLine("API Key 未设置。请确保环境变量 'DASHSCOPE_API_KEY' 已设置。");
            return;
        }

        // 设置请求 URL 和内容
        string url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation";
        // 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
        string jsonContent = @"{
            ""model"": ""qwen-plus"", 
            ""input"": {
                ""messages"": [
                    {
                        ""role"": ""system"",
                        ""content"": ""You are a helpful assistant.""
                    },
                    {
                        ""role"": ""user"",
                        ""content"": ""你是谁？""
                    }
                ]
            },
            ""parameters"": {
                ""result_format"": ""message""
            }
        }";

        // 发送请求并获取响应
        string result = await SendPostRequestAsync(url, jsonContent, apiKey);

        // 输出结果
        Console.WriteLine(result);
    }

    private static async Task&lt;string&gt; SendPostRequestAsync(string url, string jsonContent, string apiKey)
    {
        using (var content = new StringContent(jsonContent, Encoding.UTF8, "application/json"))
        {
            // 设置请求头
            httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
            httpClient.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));

            // 发送请求并获取响应
            HttpResponseMessage response = await httpClient.PostAsync(url, content);

            // 处理响应
            if (response.IsSuccessStatusCode)
            {
                return await response.Content.ReadAsStringAsync();
            }
            else
            {
                return $"请求失败: {response.StatusCode}";
            }
        }
    }
}</code></pre></div><p>DashScope 未提供 Go 的 SDK。如需通过 OpenAI Go SDK调用，请参考本文的 <a href="https://help.aliyun.com/zh/model-studio/qwen-api-reference/#0d97c51c65umq">OpenAI-Go</a> 章节。</p><div><pre><code>package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "log"
    "net/http"
    "os"
)

type Message struct {
    Role    string `json:"role"`
    Content string `json:"content"`
}

type Input struct {
    Messages []Message `json:"messages"`
}

type Parameters struct {
    ResultFormat string `json:"result_format"`
}

type RequestBody struct {
    Model      string     `json:"model"`
    Input      Input      `json:"input"`
    Parameters Parameters `json:"parameters"`
}

func main() {
    // 创建 HTTP 客户端
    client := &amp;http.Client{}

    // 构建请求体
    requestBody := RequestBody{
        // 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
        Model: "qwen-plus",
        Input: Input{
            Messages: []Message{
                {
                    Role:    "system",
                    Content: "You are a helpful assistant.",
                },
                {
                    Role:    "user",
                    Content: "你是谁？",
                },
            },
        },
        Parameters: Parameters{
            ResultFormat: "message",
        },
    }

    jsonData, err := json.Marshal(requestBody)
    if err != nil {
        log.Fatal(err)
    }

    // 创建 POST 请求
    req, err := http.NewRequest("POST", "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation", bytes.NewBuffer(jsonData))
    if err != nil {
        log.Fatal(err)
    }

    // 设置请求头
    // 若没有配置环境变量，请用百炼API Key将下行替换为：apiKey := "sk-xxx"
    apiKey := os.Getenv("DASHSCOPE_API_KEY")
    req.Header.Set("Authorization", "Bearer "+apiKey)
    req.Header.Set("Content-Type", "application/json")

    // 发送请求
    resp, err := client.Do(req)
    if err != nil {
        log.Fatal(err)
    }
    defer resp.Body.Close()

    // 读取响应体
    bodyText, err := io.ReadAll(resp.Body)
    if err != nil {
        log.Fatal(err)
    }

    // 打印响应内容
    fmt.Printf("%s\n", bodyText)
}</code></pre></div><section><blockquote>相关文档： <a href="https://help.aliyun.com/zh/model-studio/stream">流式输出</a> 。</blockquote><p>文本生成模型</p><p>多模态模型</p><p>Python</p><p>Java</p><p>curl</p><div><pre><code>import java.util.Arrays;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.alibaba.dashscope.aigc.generation.Generation;
import com.alibaba.dashscope.aigc.generation.GenerationParam;
import com.alibaba.dashscope.aigc.generation.GenerationResult;
import com.alibaba.dashscope.common.Message;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.utils.JsonUtils;
import io.reactivex.Flowable;
import java.lang.System;

public class Main {
    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    private static void handleGenerationResult(GenerationResult message) {
        System.out.println(JsonUtils.toJson(message));
    }
    public static void streamCallWithMessage(Generation gen, Message userMsg)
            throws NoApiKeyException, ApiException, InputRequiredException {
        GenerationParam param = buildGenerationParam(userMsg);
        Flowable&lt;GenerationResult&gt; result = gen.streamCall(param);
        result.blockingForEach(message -&gt; handleGenerationResult(message));
    }
    private static GenerationParam buildGenerationParam(Message userMsg) {
        return GenerationParam.builder()
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                // 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
                .model("qwen-plus")
                .messages(Arrays.asList(userMsg))
                .resultFormat(GenerationParam.ResultFormat.MESSAGE)
                .incrementalOutput(true)
                .build();
    }
    public static void main(String[] args) {
        try {
            Generation gen = new Generation();
            Message userMsg = Message.builder().role(Role.USER.getValue()).content("你是谁？").build();
            streamCallWithMessage(gen, userMsg);
        } catch (ApiException | NoApiKeyException | InputRequiredException  e) {
            logger.error("An exception occurred: {}", e.getMessage());
        }
        System.exit(0);
    }
}</code></pre></div><p>Python</p><p>Java</p><p>curl</p><div><pre><code>import java.util.Arrays;
import java.util.Collections;

import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import io.reactivex.Flowable;
import com.alibaba.dashscope.utils.Constants;

public class Main {

    // 若使用新加坡地域的模型，请取消下列注释
    //  static {Constants.baseHttpApiUrl="https://dashscope-intl.aliyuncs.com/api/v1";}

    public static void streamCall()
            throws ApiException, NoApiKeyException, UploadFileException {
        MultiModalConversation conv = new MultiModalConversation();
        MultiModalMessage userMessage = MultiModalMessage.builder().role(Role.USER.getValue())
                .content(Arrays.asList(Collections.singletonMap("image", "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"),
                        Collections.singletonMap("text", "图中描绘的是什么景象？"))).build();
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                // 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                .model("qwen3-vl-plus")  // 可按需更换为其它多模态模型，并修改相应的 messages
                .messages(Arrays.asList(userMessage))
                .incrementalOutput(true)
                .build();
        Flowable&lt;MultiModalConversationResult&gt; result = conv.streamCall(param);
        result.blockingForEach(item -&gt; {
            try {
                var content = item.getOutput().getChoices().get(0).getMessage().getContent();
                    // 判断content是否存在且不为空
                if (content != null &amp;&amp;  !content.isEmpty()) {
                    System.out.println(content.get(0).get("text"));
                    }
            } catch (Exception e) {
                System.out.println(e.getMessage());
            }
        });
    }

    public static void main(String[] args) {
        try {
            streamCall();
        } catch (ApiException | NoApiKeyException | UploadFileException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }
}</code></pre></div><div><pre><code># ======= 重要提示 =======
# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
# === 执行时请删除该注释 ===

curl -X POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H 'Content-Type: application/json' \
-H 'X-DashScope-SSE: enable' \
-d '{
    "model": "qwen3-vl-plus",
    "input":{
        "messages":[
            {
                "role": "user",
                "content": [
                    {"image": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"},
                    {"text": "图中描绘的是什么景象？"}
                ]
            }
        ]
    },
    "parameters": {
        "incremental_output": true
    }
}'</code></pre></div></section><section><blockquote>关于大模型分析图像的更多用法，请参见 <a href="https://help.aliyun.com/zh/model-studio/vision">图像与视频理解</a> 。</blockquote><p>Python</p><p>Java</p><p>curl</p><div><pre><code>import os
import dashscope

messages = [
    {
        "role": "user",
        "content": [
            {"image": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"},
            {"image": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/tiger.png"},
            {"image": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/rabbit.png"},
            {"text": "这些是什么?"}
        ]
    }
]
response = dashscope.MultiModalConversation.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    model='qwen-vl-max', # 此处以qwen-vl-max为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    messages=messages
    )
print(response)</code></pre></div><div><pre><code>// Copyright (c) Alibaba, Inc. and its affiliates.

import java.util.Arrays;
import java.util.Collections;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import com.alibaba.dashscope.utils.JsonUtils;
public class Main {
    public static void simpleMultiModalConversationCall()
            throws ApiException, NoApiKeyException, UploadFileException {
        MultiModalConversation conv = new MultiModalConversation();
        MultiModalMessage userMessage = MultiModalMessage.builder().role(Role.USER.getValue())
                .content(Arrays.asList(
                        Collections.singletonMap("image", "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"),
                        Collections.singletonMap("image", "https://dashscope.oss-cn-beijing.aliyuncs.com/images/tiger.png"),
                        Collections.singletonMap("image", "https://dashscope.oss-cn-beijing.aliyuncs.com/images/rabbit.png"),
                        Collections.singletonMap("text", "这些是什么?"))).build();
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                // 此处以qwen-vl-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
                .model("qwen-vl-plus")
                .message(userMessage)
                .build();
        MultiModalConversationResult result = conv.call(param);
        System.out.println(JsonUtils.toJson(result));
    }

    public static void main(String[] args) {
        try {
            simpleMultiModalConversationCall();
        } catch (ApiException | NoApiKeyException | UploadFileException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }
}</code></pre></div></section><section><blockquote>以下为传入视频帧的示例代码，关于更多用法（如传入视频文件），请参见 <a href="https://help.aliyun.com/zh/model-studio/vision#80dbf6ca8fh6s">视觉理解</a> 。</blockquote><p>Python</p><p>Java</p><p>curl</p><div><pre><code>from http import HTTPStatus
import os
# dashscope版本需要不低于1.20.10
import dashscope

messages = [{"role": "user",
             "content": [
                 {"video":["https://img.alicdn.com/imgextra/i3/O1CN01K3SgGo1eqmlUgeE9b_!!6000000003923-0-tps-3840-2160.jpg",
                           "https://img.alicdn.com/imgextra/i4/O1CN01BjZvwg1Y23CF5qIRB_!!6000000003000-0-tps-3840-2160.jpg",
                           "https://img.alicdn.com/imgextra/i4/O1CN01Ib0clU27vTgBdbVLQ_!!6000000007859-0-tps-3840-2160.jpg",
                           "https://img.alicdn.com/imgextra/i1/O1CN01aygPLW1s3EXCdSN4X_!!6000000005710-0-tps-3840-2160.jpg"]},
                 {"text": "描述这个视频的具体过程"}]}]
response = dashscope.MultiModalConversation.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    model='qwen-vl-max-latest',  # 此处以qwen-vl-max-latest为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    messages=messages
)
if response.status_code == HTTPStatus.OK:
    print(response)
else:
    print(response.code)
    print(response.message)</code></pre></div><div><pre><code>// DashScope SDK版本需要不低于2.16.7
import java.util.Arrays;
import java.util.Collections;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import com.alibaba.dashscope.utils.JsonUtils;
public class Main {
    // 此处以qwen-vl-max-latest为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    private static final String MODEL_NAME = "qwen-vl-max-latest";
    public static void videoImageListSample() throws ApiException, NoApiKeyException, UploadFileException {
        MultiModalConversation conv = new MultiModalConversation();
        MultiModalMessage systemMessage = MultiModalMessage.builder()
                .role(Role.SYSTEM.getValue())
                .content(Arrays.asList(Collections.singletonMap("text", "You are a helpful assistant.")))
                .build();
        MultiModalMessage userMessage = MultiModalMessage.builder()
                .role(Role.USER.getValue())
                .content(Arrays.asList(Collections.singletonMap("video", Arrays.asList("https://img.alicdn.com/imgextra/i3/O1CN01K3SgGo1eqmlUgeE9b_!!6000000003923-0-tps-3840-2160.jpg",
                                "https://img.alicdn.com/imgextra/i4/O1CN01BjZvwg1Y23CF5qIRB_!!6000000003000-0-tps-3840-2160.jpg",
                                "https://img.alicdn.com/imgextra/i4/O1CN01Ib0clU27vTgBdbVLQ_!!6000000007859-0-tps-3840-2160.jpg",
                                "https://img.alicdn.com/imgextra/i1/O1CN01aygPLW1s3EXCdSN4X_!!6000000005710-0-tps-3840-2160.jpg")),
                        Collections.singletonMap("text", "描述这个视频的具体过程")))
                .build();
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                .model(MODEL_NAME).message(systemMessage)
                .message(userMessage).build();
        MultiModalConversationResult result = conv.call(param);
        System.out.print(JsonUtils.toJson(result));
    }
    public static void main(String[] args) {
        try {
            videoImageListSample();
        } catch (ApiException | NoApiKeyException | UploadFileException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }
}</code></pre></div><div><pre><code>curl -X POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H 'Content-Type: application/json' \
-d '{
  "model": "qwen-vl-max-latest",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "video": [
              "https://img.alicdn.com/imgextra/i3/O1CN01K3SgGo1eqmlUgeE9b_!!6000000003923-0-tps-3840-2160.jpg",
              "https://img.alicdn.com/imgextra/i4/O1CN01BjZvwg1Y23CF5qIRB_!!6000000003000-0-tps-3840-2160.jpg",
              "https://img.alicdn.com/imgextra/i4/O1CN01Ib0clU27vTgBdbVLQ_!!6000000007859-0-tps-3840-2160.jpg",
              "https://img.alicdn.com/imgextra/i1/O1CN01aygPLW1s3EXCdSN4X_!!6000000005710-0-tps-3840-2160.jpg"
            ]
          },
          {
            "text": "描述这个视频的具体过程"
          }
        ]
      }
    ]
  }
}'</code></pre></div></section><p>音频理解</p><section><blockquote>关于大模型分析音频的更多用法，请参见 <a href="https://help.aliyun.com/zh/model-studio/audio-language-model">音频理解-Qwen-Audio</a> 。</blockquote><p>Python</p><p>Java</p><p>curl</p><div><pre><code>import os
import dashscope

messages = [
    {
        "role": "user",
        "content": [
            {"audio": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"},
            {"text": "这段音频在说什么?"}
        ]
    }
]
response = dashscope.MultiModalConversation.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    model='qwen2-audio-instruct', # 此处以qwen2-audio-instruct为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    messages=messages
    )
print(response)</code></pre></div><div><pre><code>import java.util.Arrays;
import java.util.Collections;
import java.lang.System;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversation;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationParam;
import com.alibaba.dashscope.aigc.multimodalconversation.MultiModalConversationResult;
import com.alibaba.dashscope.common.MultiModalMessage;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.exception.UploadFileException;
import com.alibaba.dashscope.utils.JsonUtils;
public class Main {
    public static void simpleMultiModalConversationCall()
            throws ApiException, NoApiKeyException, UploadFileException {
        MultiModalConversation conv = new MultiModalConversation();
        MultiModalMessage userMessage = MultiModalMessage.builder().role(Role.USER.getValue())
                .content(Arrays.asList(Collections.singletonMap("audio", "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"),
                        Collections.singletonMap("text", "这段音频在说什么?"))).build();
        MultiModalConversationParam param = MultiModalConversationParam.builder()
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                // 此处以qwen2-audio-instruct为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
                .model("qwen2-audio-instruct")
                .message(userMessage)
                .build();
        MultiModalConversationResult result = conv.call(param);
        System.out.println(JsonUtils.toJson(result));
    }

    public static void main(String[] args) {
        try {
            simpleMultiModalConversationCall();
        } catch (ApiException | NoApiKeyException | UploadFileException e) {
            System.out.println(e.getMessage());
        }
        System.exit(0);
    }
}</code></pre></div></section><p>Python</p><p>Java</p><p>curl</p><div><pre><code>import os
import dashscope

messages = [
    {'role': 'system', 'content': 'You are a helpful assistant.'},
    {'role': 'user', 'content': '杭州明天天气是什么？'}
    ]
response = dashscope.Generation.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    model="qwen-plus", # 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    messages=messages,
    enable_search=True,
    result_format='message'
    )
print(response)</code></pre></div><div><pre><code>// 建议dashscope SDK的版本 &gt;= 2.12.0
import java.util.Arrays;
import java.lang.System;
import com.alibaba.dashscope.aigc.generation.Generation;
import com.alibaba.dashscope.aigc.generation.GenerationParam;
import com.alibaba.dashscope.aigc.generation.GenerationResult;
import com.alibaba.dashscope.common.Message;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.utils.JsonUtils;

public class Main {
    public static GenerationResult callWithMessage() throws ApiException, NoApiKeyException, InputRequiredException {
        Generation gen = new Generation();
        Message systemMsg = Message.builder()
                .role(Role.SYSTEM.getValue())
                .content("You are a helpful assistant.")
                .build();
        Message userMsg = Message.builder()
                .role(Role.USER.getValue())
                .content("明天杭州什么天气？")
                .build();
        GenerationParam param = GenerationParam.builder()
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                // 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
                .model("qwen-plus")
                .messages(Arrays.asList(systemMsg, userMsg))
                .resultFormat(GenerationParam.ResultFormat.MESSAGE)
                .enableSearch(true)
                .build();
        return gen.call(param);
    }
    public static void main(String[] args) {
        try {
            GenerationResult result = callWithMessage();
            System.out.println(JsonUtils.toJson(result));
        } catch (ApiException | NoApiKeyException | InputRequiredException e) {
            // 使用日志框架记录异常信息
            System.err.println("An error occurred while calling the generation service: " + e.getMessage());
        }
        System.exit(0);
    }
}</code></pre></div><div><pre><code>curl -X POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "qwen-plus",
    "input":{
        "messages":[      
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "明天杭州天气如何？"
            }
        ]
    },
    "parameters": {
        "enable_search": true,
        "result_format": "message"
    }
}'</code></pre></div><section><blockquote>完整的Function Calling 流程代码请参见 <a href="https://help.aliyun.com/zh/model-studio/qwen-function-calling#0f0fcbd808d8o">Function Calling</a> 。</blockquote><p>Python</p><p>Java</p><p>curl</p><div><pre><code>import os
import dashscope

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "当你想知道现在的时间时非常有用。",
            "parameters": {}
        }
    },  
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "当你想查询指定城市的天气时非常有用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "城市或县区，比如北京市、杭州市、余杭区等。"
                    }
                }
            },
            "required": [
                "location"
            ]
        }
    }
]
messages = [{"role": "user", "content": "杭州天气怎么样"}]
response = dashscope.Generation.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    model='qwen-plus',  # 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    messages=messages,
    tools=tools,
    result_format='message'
)
print(response)</code></pre></div><div><pre><code>import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import com.alibaba.dashscope.aigc.conversation.ConversationParam.ResultFormat;
import com.alibaba.dashscope.aigc.generation.Generation;
import com.alibaba.dashscope.aigc.generation.GenerationParam;
import com.alibaba.dashscope.aigc.generation.GenerationResult;
import com.alibaba.dashscope.common.Message;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.tools.FunctionDefinition;
import com.alibaba.dashscope.tools.ToolFunction;
import com.alibaba.dashscope.utils.JsonUtils;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.github.victools.jsonschema.generator.Option;
import com.github.victools.jsonschema.generator.OptionPreset;
import com.github.victools.jsonschema.generator.SchemaGenerator;
import com.github.victools.jsonschema.generator.SchemaGeneratorConfig;
import com.github.victools.jsonschema.generator.SchemaGeneratorConfigBuilder;
import com.github.victools.jsonschema.generator.SchemaVersion;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public class Main {
    public class GetWeatherTool {
        private String location;
        public GetWeatherTool(String location) {
            this.location = location;
        }
        public String call() {
            return location+"今天是晴天";
        }
    }
    public class GetTimeTool {
        public GetTimeTool() {
        }
        public String call() {
            LocalDateTime now = LocalDateTime.now();
            DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
            String currentTime = "当前时间：" + now.format(formatter) + "。";
            return currentTime;
        }
    }
    public static void SelectTool()
            throws NoApiKeyException, ApiException, InputRequiredException {
        SchemaGeneratorConfigBuilder configBuilder =
                new SchemaGeneratorConfigBuilder(SchemaVersion.DRAFT_2020_12, OptionPreset.PLAIN_JSON);
        SchemaGeneratorConfig config = configBuilder.with(Option.EXTRA_OPEN_API_FORMAT_VALUES)
                .without(Option.FLATTENED_ENUMS_FROM_TOSTRING).build();
        SchemaGenerator generator = new SchemaGenerator(config);
        ObjectNode jsonSchema_weather = generator.generateSchema(GetWeatherTool.class);
        ObjectNode jsonSchema_time = generator.generateSchema(GetTimeTool.class);
        FunctionDefinition fdWeather = FunctionDefinition.builder().name("get_current_weather").description("获取指定地区的天气")
                .parameters(JsonUtils.parseString(jsonSchema_weather.toString()).getAsJsonObject()).build();
        FunctionDefinition fdTime = FunctionDefinition.builder().name("get_current_time").description("获取当前时刻的时间")
                .parameters(JsonUtils.parseString(jsonSchema_time.toString()).getAsJsonObject()).build();
        Message systemMsg = Message.builder().role(Role.SYSTEM.getValue())
                .content("You are a helpful assistant. When asked a question, use tools wherever possible.")
                .build();
        Message userMsg = Message.builder().role(Role.USER.getValue()).content("杭州天气").build();
        List&lt;Message&gt; messages = new ArrayList&lt;&gt;();
        messages.addAll(Arrays.asList(systemMsg, userMsg));
        GenerationParam param = GenerationParam.builder()
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                // 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
                .model("qwen-plus")
                .messages(messages)
                .resultFormat(ResultFormat.MESSAGE)
                .tools(Arrays.asList(
                        ToolFunction.builder().function(fdWeather).build(),
                        ToolFunction.builder().function(fdTime).build()))
                .build();
        Generation gen = new Generation();
        GenerationResult result = gen.call(param);
        System.out.println(JsonUtils.toJson(result));
    }
    public static void main(String[] args) {
        try {
            SelectTool();
        } catch (ApiException | NoApiKeyException | InputRequiredException e) {
            System.out.println(String.format("Exception %s", e.getMessage()));
        }
        System.exit(0);
    }
}</code></pre></div></section><div><pre><code># 您的Dashscope Python SDK版本需要不低于 1.19.0。
import asyncio
import platform
import os
from dashscope.aigc.generation import AioGeneration

async def main():
    response = await AioGeneration.call(
        # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
        api_key=os.getenv('DASHSCOPE_API_KEY'),
        model="qwen-plus",  # 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
        messages=[{"role": "user", "content": "你是谁"}],
        result_format="message",
    )
    print(response)

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())</code></pre></div><p>Python</p><p>Java</p><p>curl</p><div><pre><code>import os
import dashscope

messages = [
        {'role': 'system', 'content': 'you are a helpful assisstant'},
        # 请将 '{FILE_ID}'替换为您实际对话场景所使用的 fileid
        {'role':'system','content':f'fileid://{FILE_ID}'},
        {'role': 'user', 'content': '这篇文章讲了什么'}]
response = dashscope.Generation.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    model="qwen-long",
    messages=messages,
    result_format='message'
)
print(response)</code></pre></div><div><pre><code>import java.util.Arrays;
import com.alibaba.dashscope.aigc.generation.Generation;
import com.alibaba.dashscope.aigc.generation.GenerationParam;
import com.alibaba.dashscope.aigc.generation.GenerationResult;
import com.alibaba.dashscope.common.Message;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.utils.JsonUtils;

public class Main {

    public static GenerationResult callWithFile() throws ApiException, NoApiKeyException, InputRequiredException {
        Generation gen = new Generation();

        Message systemMsg = Message.builder()
                .role(Role.SYSTEM.getValue())
                .content("you are a helpful assistant")
                .build();

        Message fileSystemMsg = Message.builder()
                .role(Role.SYSTEM.getValue())
                // 请将 '{FILE_ID}'替换为您实际对话场景所使用的 file-id
                .content("fileid://{FILE_ID}")
                .build();

        Message userMsg = Message.builder()
                .role(Role.USER.getValue())
                .content("这篇文章讲了什么")
                .build();

        GenerationParam param = GenerationParam.builder()
                // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("sk-xxx")
                .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                .model("qwen-long")
                .messages(Arrays.asList(systemMsg, fileSystemMsg, userMsg))
                .resultFormat(GenerationParam.ResultFormat.MESSAGE)
                .build();

        return gen.call(param);
    }

    public static void main(String[] args) {
        try {
            GenerationResult result = callWithFile();
            System.out.println(JsonUtils.toJson(result));
        } catch (ApiException | NoApiKeyException | InputRequiredException e) {
            System.err.println("调用 DashScope API 出错: " + e.getMessage());
            e.printStackTrace();
        }
    }
}</code></pre></div></td></tr><tr><td rowspan="1" colspan="1"><p><b>model </b><code><i>string</i></code> <b>（必选）</b></p><p>模型名称。</p><p>支持的模型：Qwen 大语言模型（商业版、开源版）、Qwen-VL、Qwen-Coder <span>、千问Audio</span> 、数学模型。</p><p><b>具体模型名称和计费，请参见</b> <a href="https://help.aliyun.com/zh/model-studio/models#9f8890ce29g5u">文本生成-千问</a> 。</p></td></tr><tr><td rowspan="1" colspan="1"><p><b>messages </b><code><i>array</i></code> <b>（必选）</b></p><p>传递给大模型的上下文，按对话顺序排列。</p><blockquote>通过HTTP调用时，请将 <b>messages </b>放入 <b>input</b> 对象中。</blockquote><p><span></span></p><p><b>消息类型</b></p><p></p><p>User Message <code><i>object</i></code> <b>（必选）</b></p><p>用户消息，用于向模型传递问题、指令或上下文等。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>content </b><code><i>string 或 array</i></code> <b>（必选）</b></p><p>消息内容。若输入只有文本，则为 string 类型；若输入包含图像等多模态数据，或启用显式缓存，则为 array 类型。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>text </b><code><i>string</i></code> <b>（必选）</b></p><p>输入的文本。</p><p><b>fps </b><code><i>float</i></code> （可选）</p><p>每秒抽帧数。取值范围为 [0.1, 10]，默认值为2.0。</p><p><span></span></p><p><b>功能说明</b></p><p></p><div><p>fps有两个功能：</p><ul><li><p>输入视频文件时，控制抽帧频率，每 秒抽取一帧。</p><blockquote>适用于 <a href="https://help.aliyun.com/zh/model-studio/vision">Qwen-VL 模型</a> 与 <a href="https://help.aliyun.com/zh/model-studio/visual-reasoning">QVQ模型</a> 。</blockquote></li><li><p>告知模型相邻帧之间的时间间隔，帮助其更好地理解视频的时间动态。同时适用于输入视频文件与图像列表时。该功能同时支持视频文件和图像列表输入，适用于事件时间定位或分段内容摘要等场景。</p><blockquote>支持Qwen3.5、 <code>Qwen3-VL</code> 、 <code>Qwen2.5-VL</code> 与QVQ模型。</blockquote></li></ul><p>较大的 <code>fps</code> 适合高速运动的场景（如体育赛事、动作电影等），较小的 <code>fps</code> 适合长视频或内容偏静态的场景。</p></div><p><span></span></p><p><b>示例值</b></p><p></p><div><ul><li><p>图像列表传入： <code>{"video":["https://xx1.jpg",...,"https://xxn.jpg"]，"fps":2}</code></p></li><li><p>视频文件传入： <code>{"video": "https://xx1.mp4"，"fps":2}</code></p></li></ul></div><section><p><b>max_frames </b><code><i>integer</i></code> （可选）</p><p>视频抽取帧数的上限。当按 <code>fps</code> 计算的帧数超过 <code>max_frames</code> 时，系统将自动调整为：在 <code>max_frames</code> 内均匀抽帧，确保总帧数不超过限制。</p><p><span></span></p><p><b>取值范围</b></p><p></p><div><ul><li><p>qwen3.5系列、 <code>qwen3-vl-plus</code> 系列、 <code>qwen3-vl-flash</code> 系列、 <code>qwen3-vl-235b-a22b-thinking</code> 、 <code>qwen3-vl-235b-a22b-instruct</code> ：最大值和默认值均为 2000</p></li><li><p><code>qwen-vl-max</code> 、 <code>qwen-vl-max-latest</code> 、 <code>qwen-vl-max-0813</code> 、 <code>qwen-vl-plus</code> 、 <code>qwen-vl-plus-latest</code> 、 <code>qwen-vl-plus-0815</code> <code>、qwen-vl-plus-0710</code> ：最大值和默认值均为 512。</p></li></ul></div><p><span></span></p><p><b>示例值</b></p><p></p><p><code>{"type": "video_url","video_url": {"url":"https://xxxx.mp4"},"max_frame": 2000}</code></p><blockquote>使用 OpenAI 兼容API调用时，不支持自定义 <code>max_frames</code> 参数，API 将自动使用各模型对应的默认值。</blockquote></section><p><b>min_pixels </b><code><i>integer</i></code> （可选）</p><p>设定输入图像或视频帧的最小像素阈值。当输入图像或视频帧的像素小于 <code>min_pixels</code> 时，会将其进行放大，直到总像素高于 <code>min_pixels</code> 。</p><p><span></span></p><p><b>取值范围</b></p><p></p><div><ul><li><p><b>输入图像：</b></p><ul><li><p><code>Qwen3.5</code> 、 <code>Qwen3-VL</code> ：默认值和最小值均为： <code>65536</code></p></li><li><p><code>qwen-vl-max</code> 、 <code>qwen-vl-max-latest</code> 、 <code>qwen-vl-max-0813</code> 、 <code>qwen-vl-plus</code> 、 <code>qwen-vl-plus-latest</code> 、 <code>qwen-vl-plus-0815</code> <code>、qwen-vl-plus-0710</code> ：默认值和最小值均为 <code>4096</code></p></li><li><p>其他 <code>qwen-vl-plus</code> 模型、其他 <code>qwen-vl-max</code> 模型、 <code>Qwen2.5-VL</code> 开源系列及 <code>QVQ</code> 系列模型：默认值和最小值均为 <code>3136</code></p></li></ul></li><li><p><b>输入视频文件或图像列表：</b></p><ul><li><p><code>Qwen3.5</code> 、Qwen3-VL（包括商业版和开源版）、 <code>qwen-vl-max</code> 、 <code>qwen-vl-max-latest</code> 、 <code>qwen-vl-max-0813</code> 、 <code>qwen-vl-plus</code> 、 <code>qwen-vl-plus-latest</code> 、 <code>qwen-vl-plus-0815</code> <code>、qwen-vl-plus-0710</code> ：默认值为 <code>65536</code> ，最小值为 <code>4096</code></p></li><li><p>其他 <code>qwen-vl-plus</code> 模型、其他 <code>qwen-vl-max</code> 模型、 <code>Qwen2.5-VL</code> 开源系列及 <code>QVQ</code> 系列模型：默认值为 <code>50176</code> ，最小值为 <code>3136</code></p></li></ul></li></ul></div><p><span></span></p><p><b>示例值</b></p><p></p><div><ul><li><p>输入图像： <code>{"type": "image_url","image_url": {"url":"https://xxxx.jpg"},"min_pixels": 65536}</code></p></li><li><p>输入视频文件时： <code>{"type": "video_url","video_url": {"url":"https://xxxx.mp4"},"min_pixels": 65536}</code></p></li><li><p>输入图像列表时： <code>{"type": "video","video": ["https://xx1.jpg",...,"https://xxn.jpg"],"min_pixels": 65536}</code></p></li></ul></div><p><b>max_pixels </b><code><i>integer</i></code> （可选）</p><p>用于设定输入图像或视频帧的最大像素阈值。当输入图像或视频的像素在 <code>[min_pixels, max_pixels]</code> 区间内时，模型会按原图进行识别。当输入图像像素大于 <code>max_pixels</code> 时，会将图像进行缩小，直到总像素低于 <code>max_pixels</code> 。</p><p><span></span></p><p><b>取值范围</b></p><p></p><div><ul><li><p><b>输入图像：</b></p><p><code>max_pixels</code> 的取值与是否开启 <code><a href="https://help.aliyun.com/zh/model-studio/qwen-api-reference/#0edad44583knr">vl_high_resolution_images</a></code> 参数有关。</p><ul><li><p>当 <code>vl_high_resolution_images</code> 为 <code>False</code> 时：</p><ul><li><p><code>Qwen3.5</code> 、 <code>Qwen3-VL</code> ：默认值为 <code>2621440</code> ，最大值为： <code>16777216</code></p></li><li><p><code>qwen-vl-max</code> 、 <code>qwen-vl-max-latest</code> 、 <code>qwen-vl-max-0813</code> 、 <code>qwen-vl-plus</code> 、 <code>qwen-vl-plus-latest</code> 、 <code>qwen-vl-plus-0815</code> <code>、qwen-vl-plus-0710</code> ：默认值为 <code>1310720</code> ，最大值为： <code>16777216</code></p></li><li><p>其他 <code>qwen-vl-plus</code> 模型、其他 <code>qwen-vl-max</code> 模型、 <code>Qwen2.5-VL</code> 开源系列及 <code>QVQ</code> 系列模型：默认值为 <code>1003520</code> ，最大值为 <code>12845056</code></p></li></ul></li></ul><ul><li><p>当 <code>vl_high_resolution_images</code> 为 <code>True</code> 时：</p><ul><li><p><code>Qwen3.5</code> 、Qwen3-VL、 <code>qwen-vl-max</code> 、 <code>qwen-vl-max-latest</code> 、 <code>qwen-vl-max-0813</code> 、 <code>qwen-vl-plus</code> 、 <code>qwen-vl-plus-latest</code> 、 <code>qwen-vl-plus-0815</code> <code>、qwen-vl-plus-0710</code> ： <code>max_pixels</code> 无效，输入图像的最大像素固定为 <code>16777216</code></p></li><li><p>其他 <code>qwen-vl-plus</code> 模型、其他 <code>qwen-vl-max</code> 模型、 <code>Qwen2.5-VL</code> 开源系列及 <code>QVQ</code> 系列模型： <code>max_pixels</code> 无效，输入图像的最大像素固定为 <code>12845056</code></p></li></ul></li></ul></li><li><p><b>输入视频文件或图像列表：</b></p><ul><li><p><code>qwen3.5系列、qwen3-vl-plus</code> 系列、 <code>qwen3-vl-flash</code> 系列、 <code>qwen3-vl-235b-a22b-thinking</code> 、 <code>qwen3-vl-235b-a22b-instruct</code> ：默认值为 <code>655360</code> ，最大值为 <code>2048000</code></p></li><li><p>其他 <code>Qwen3-VL</code> 开源模型、 <code>qwen-vl-max</code> 、 <code>qwen-vl-max-latest</code> 、 <code>qwen-vl-max-0813</code> 、 <code>qwen-vl-plus</code> 、 <code>qwen-vl-plus-latest</code> 、 <code>qwen-vl-plus-0815</code> <code>、qwen-vl-plus-0710</code> ：默认值 <code>655360</code> ，最大值为 <code>786432</code></p></li><li><p>其他 <code>qwen-vl-plus</code> 模型、其他 <code>qwen-vl-max</code> 模型、 <code>Qwen2.5-VL</code> 开源系列及 <code>QVQ</code> 系列模型：默认值为 <code>501760</code> ，最大值为 <code>602112</code></p></li></ul></li></ul></div><p><span></span></p><p><b>示例值</b></p><p></p><div><ul><li><p>输入图像： <code>{"type": "image_url","image_url": {"url":"https://xxxx.jpg"},"max_pixels": 8388608}</code></p></li><li><p>输入视频文件时： <code>{"type": "video_url","video_url": {"url":"https://xxxx.mp4"},"max_pixels": 655360}</code></p></li><li><p>输入图像列表时： <code>{"type": "video","video": ["https://xx1.jpg",...,"https://xxn.jpg"],"max_pixels": 655360}</code></p></li></ul></div><p><b>total_pixels </b><code><i>integer</i></code> （可选）</p><p>用于限制从视频中抽取的所有帧的总像素（单帧图像像素 × 总帧数）。如果视频总像素超过此限制，系统将对视频帧进行缩放，但仍会确保单帧图像的像素值在 <code>[min_pixels, max_pixels]</code> 范围内。适用于 Qwen-VL、QVQ 模型。</p><p>对于抽帧数量较多的长视频，可适当降低此值以减少Token消耗和处理时间，但这可能会导致图像细节丢失。</p><p><span></span></p><p><b>取值范围</b></p><p></p><div><ul><li><p>qwen3.5系列、 <code>qwen3-vl-plus</code> 系列、 <code>qwen3-vl-flash</code> 系列、 <code>qwen3-vl-235b-a22b-thinking</code> 、 <code>qwen3-vl-235b-a22b-instruct</code> ：默认值和最小值均为134217728，该值对应 <code>131072</code> 个图像 Token（每 32×32 像素对应 1 个图像 Token）。</p></li><li><p>其他 <code>Qwen3-VL</code> 开源模型、 <code>qwen-vl-max</code> 、 <code>qwen-vl-max-latest</code> 、 <code>qwen-vl-max-0813</code> 、 <code>qwen-vl-plus</code> 、 <code>qwen-vl-plus-latest</code> 、 <code>qwen-vl-plus-0815</code> <code>、qwen-vl-plus-0710</code> ：默认值和最小值均为 <code>67108864</code> ，该值对应 <code>65536</code> 个图像 Token（每 32×32 像素对应 1 个图像 Token）。</p></li><li><p>其他 <code>qwen-vl-plus</code> 模型、其他 <code>qwen-vl-max</code> 模型、 <code>Qwen2.5-VL</code> 开源系列及 <code>QVQ</code> 系列模型：默认值和最小值均为 <code>51380224</code> ，该值对应 <code>65536</code> 个图像 Token（每 28×28 像素对应 1 个图像 Token）。</p></li></ul></div><p><span></span></p><p><b>示例值</b></p><p></p><div><ul><li><p>输入视频文件时： <code>{"type": "video_url","video_url": {"url":"https://xxxx.mp4"},"total_pixels": 134217728}</code></p></li><li><p>输入图像列表时： <code>{"type": "video","video": ["https://xx1.jpg",...,"https://xxn.jpg"],"total_pixels": 134217728}</code></p></li></ul></div><section><p><b>audio </b><code><i>string</i></code></p><blockquote>模型为 <span>音频理解</span> 时，是必选参数，如模型为 <span>qwen2-audio-instruct</span> 等。</blockquote><p>使用音频理解功能时，传入的音频文件。</p><p>示例值： <code>{"audio":"https://xxx.mp3"}</code></p></section><p><b>cache_control </b><code><i>object</i></code> <b>（可选）</b></p><p>仅支持 <a href="https://help.aliyun.com/zh/model-studio/context-cache#825f201c5fy6o">显式缓存</a> 的模型支持，用于开启显式缓存。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>type</b> <code><i>string</i></code> <b>（必选）</b></p><p>固定为 <code>ephemeral</code> 。</p><p><b>role </b><code><i>string</i></code> <b>（必选）</b></p><p>用户消息的角色，固定为 <code>user</code> 。</p><p>Assistant Message <code><i>object</i></code> （可选）</p><p>模型对用户消息的回复。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>content </b><code><i>string</i></code> （可选）</p><p>消息内容。仅当助手消息中指定 <code>tool_calls</code> 参数时非必选。</p><p><b>role </b><code><i>string</i></code> <b>（必选）</b></p><p>固定为 <code>assistant</code> 。</p><p><b>partial </b><code><i>boolean</i></code> （可选）</p><p>是否开启前缀续写。相关文档与支持的模型： <a href="https://help.aliyun.com/zh/model-studio/partial-mode">前缀续写</a> 。</p><p><b>tool_calls</b> <code><i>array</i></code> （可选）</p><p>发起 Function Calling 后，返回的工具与入参信息，包含一个或多个对象。由上一轮模型响应的 <code>tool_calls</code> 字段获得。</p><p>Tool Message <code><i>object</i></code> （可选）</p><p>工具的输出信息。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>content </b><code><i>string</i></code> <b>（必选）</b></p><p>工具函数的输出内容，必须为字符串格式。</p><p><b>role </b><code><i>string</i></code> <b>（必选）</b></p><p>固定为 <code>tool</code> 。</p><p><b>tool_call_id </b><code><i>string</i></code> <b>（可选）</b></p><p>发起 Function Calling 后返回的 id，可以通过 <code>response.output.choices[0].message.tool_calls[$index]["id"]</code> 获取，用于标记 Tool Message 对应的工具。</p></td></tr><tr><td rowspan="1" colspan="1"><p><b>temperature </b><code><i>float</i></code> （可选）</p><p>采样温度，控制模型生成文本的多样性。</p><p>temperature越高，生成的文本更多样，反之，生成的文本更确定。</p><p>取值范围： [0, 2)</p><p><span></span></p><p><b>temperature默认值</b></p><p></p><div><ul><li><p>Qwen3.5（非思考模式）、Qwen3（非思考模式）、Qwen3-Instruct系列、Qwen3-Coder系列、qwen-max系列、qwen-plus系列（非思考模式）、qwen-flash系列（非思考模式）、qwen-turbo系列（非思考模式）、qwen开源系列、qwen-coder系列、qwen2-audio-instruct、qwen-doc-turbo、qwen-vl-max-2025-08-13、Qwen3-VL（非思考）：0.7；</p></li><li><p>QVQ系列 、qwen-vl-plus-2025-07-10、qwen-vl-plus-2025-08-15: 0.5；</p></li><li><p>qwen-audio-turbo系列：0.00001；</p></li><li><p>qwen-vl系列、qwen2.5-omni-7b、qvq-72b-preview：0.01；</p></li><li><p>qwen-math系列：0；</p></li><li><p>Qwen3.5（思考模式）、Qwen3（思考模式）、Qwen3-Thinking、Qwen3-Omni-Captioner、QwQ 系列：0.6；</p></li><li><p>qwen3-max-preview（思考模式）、qwen-long系列： 1.0；</p></li><li><p>qwen-plus-character：0.92</p></li><li><p>qwen3-omni-flash系列：0.9</p></li><li><p>Qwen3-VL（思考模式）：0.8</p></li></ul></div><blockquote>通过HTTP调用时，请将 <b>temperature </b>放入 <b>parameters</b> 对象中。</blockquote><blockquote>不建议修改QVQ模型的默认 temperature 值。</blockquote></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>top_p </b><code><i>float</i></code> （可选）</p><p>核采样的概率阈值，控制模型生成文本的多样性。</p><p>top_p越高，生成的文本更多样。反之，生成的文本更确定。</p><p>取值范围：（0,1.0]。</p><p><span></span></p><p><b>top_p默认值</b></p><p></p><p>Qwen3.5（非思考模式）、Qwen3（非思考模式）、Qwen3-Instruct系列、Qwen3-Coder系列、qwen-max系列、qwen-plus系列（非思考模式）、qwen-flash系列（非思考模式）、qwen-turbo系列（非思考模式）、qwen开源系列 <span>、qwen-coder系列、qwen-long、qwen-doc-turbo、qwq-32b-preview、qwen-audio-turbo系列</span> 、qwen-vl-max-2025-08-13、Qwen3-VL（非思考模式）：0.8；</p><p><span>qwen-vl-max-2024-11-19、qwen2-vl-72b-instruct、qwen-omni-turbo 系列</span> ：0.01；</p><p>qwen-vl-plus系列、qwen-vl-max、qwen-vl-max-latest、qwen-vl-max-2025-04-08 <span>、qwen-vl-max-2025-04-02、qwen-vl-max-2025-01-25、qwen-vl-max-2024-12-30、qvq-72b-preview、qwen2-vl-2b-instruct、qwen2-vl-7b-instruct</span> 、qwen2.5-vl-3b-instruct、qwen2.5-vl-7b-instruct、qwen2.5-vl-32b-instruct、qwen2.5-vl-72b-instruct：0.001；</p><p>QVQ系列、qwen-vl-plus-2025-07-10、qwen-vl-plus-2025-08-15 <span>、qwen2-audio-instruct</span> ：0.5；</p><p>qwen3-max-preview（思考模式）、 <span>qwen-math系列、</span> Qwen3-Omni-Flash系列：1.0；</p><p>Qwen3.5（思考模式）、Qwen3（思考模式）、Qwen3-VL（思考模式）、Qwen3-Thinking、QwQ 系列、Qwen3-Omni-Captioner <span>、qwen-plus-character</span> ：0.95</p><blockquote>Java SDK中为 <b>topP</b> <i>。</i> 通过HTTP调用时，请将 <b>top_p </b>放入 <b>parameters</b> 对象中。</blockquote><blockquote>不建议修改QVQ模型的默认 top_p 值。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>top_k </b><code><i>integer</i></code> （可选）</p><p>生成过程中采样候选集的大小。例如，取值为50时，仅将单次生成中得分最高的50个Token组成随机采样的候选集。取值越大，生成的随机性越高；取值越小，生成的确定性越高。取值为None或当top_k大于100时，表示不启用top_k策略，此时仅有top_p策略生效。</p><p>取值需要大于或等于0。</p><p><span></span></p><p><b>top_k默认值</b></p><p></p><p>QVQ系列、qwen-vl-plus-2025-07-10、qwen-vl-plus-2025-08-15：10；</p><p>QwQ 系列：40；</p><p><span>qwen-math 系列、</span> 其余qwen-vl-plus系列、qwen-vl-max-2025-08-13之前的模型、 <span>qwen-audio-turbo系列、</span> qwen2.5-omni-7b <span>、qvq-72b-preview</span> ：1；</p><p>Qwen3-Omni-Flash系列：50</p><p>其余模型均为20；</p><blockquote>Java SDK中为 <b>topK</b> <i>。</i> 通过HTTP调用时，请将 <b>top_k </b>放入 <b>parameters</b> 对象中。</blockquote><blockquote>不建议修改QVQ模型的默认 top_k 值。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><p><b>enable_thinking</b> <code><i>boolean</i></code> （可选）</p><p>使用混合思考模型时，是否开启思考模式，适用于Qwen3.5、 Qwen3 、Qwen3-VL模型。相关文档： <a href="https://help.aliyun.com/zh/model-studio/deep-thinking">深度思考</a></p><p>可选值：</p><ul><li><p><code>true</code> ：开启</p><blockquote>开启后，思考内容将通过 <code>reasoning_content</code> 字段返回。</blockquote></li><li><p><code>false</code> ：不开启</p></li></ul><p>不同模型的默认值： <a href="https://help.aliyun.com/zh/model-studio/deep-thinking#78286fdc35hlw">支持的模型</a></p><blockquote>Java SDK 为enableThinking；通过HTTP调用时，请将 <b>enable_thinking</b> 放入 <b>parameters</b> 对象中。</blockquote></td></tr><tr><td rowspan="1" colspan="1"><p><b>thinking_budget</b> <code><i>integer</i></code> （可选）</p><p>思考过程的最大长度。适用于Qwen3.5、Qwen3-VL、Qwen3 的商业版与开源版模型。相关文档： <a href="https://help.aliyun.com/zh/model-studio/deep-thinking#e7c0002fe4meu">限制思考长度</a> 。</p><p>默认值为模型最大思维链长度，请参见： <a href="https://help.aliyun.com/zh/model-studio/models">模型列表</a></p><blockquote>Java SDK 为 thinkingBudget。通过HTTP调用时，请将 <b>thinking_budget</b> 放入 <b>parameters</b> 对象中。</blockquote><blockquote>默认值为模型最大思维链长度。</blockquote></td></tr><tr><td rowspan="1" colspan="1"><p><b>enable_code_interpreter</b> <code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>是否开启代码解释器功能。仅支持qwen3.5，以及思考模式下的 qwen3-max与 qwen3-max-2026-01-23、qwen3-max-preview。相关文档： <a href="https://help.aliyun.com/zh/model-studio/qwen-code-interpreter">代码解释器</a></p><p>可选值：</p><ul><li><p><code>true</code> ：开启</p></li><li><p><code>false</code> ：不开启</p></li></ul><blockquote>不支持 Java SDK。通过HTTP调用时，请将 <b>enable_code_interpreter</b> 放入 <b>parameters</b> 对象中。</blockquote></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>repetition_penalty </b><code><i>float</i></code> （可选）</p><p>模型生成时连续序列中的重复度。提高repetition_penalty时可以降低模型生成的重复度，1.0表示不做惩罚。没有严格的取值范围，只要大于0即可。</p><p><span></span></p><p><b>repetition_penalty默认值</b></p><p></p><div><ul><li><p>qwen-max、qwen-max-latest、qwen-max-2024-09-19、qwen-math系列、qwen-vl-max系列、qvq-72b-preview、qwen2-vl-72b-instruct、qwen-vl-plus-2025-01-02、qwen-vl-plus-2025-05-07、qwen-vl-plus-2025-07-10、qwen-vl-plus-2025-08-15、qwen-vl-plus-latest、qwen2.5-vl-3b-instruct、qwen2.5-vl-7b-instruct、qwen2.5-vl-32b-instruct、qwen2.5-vl-72b-instruct、 <span>qwen-audio-turbo系列、</span> QVQ系列、QwQ系列、qwq-32b-preview、Qwen3-VL： 1.0；</p></li><li><p>qwen-coder系列、qwen2.5-1.5b-instruct、qwen2.5-0.5b-instruct、qwen2-1.5b-instruct、qwen2-0.5b-instruct、qwen2-vl-2b-instruct、qwen2-vl-7b-instruct、qwen2.5-omni-7b、qwen2-audio-instruct：1.1；</p></li><li><p>qwen-vl-plus、qwen-vl-plus-2025-01-25：1.2；</p></li><li><p>其余模型为1.05。</p></li></ul></div><blockquote>Java SDK中为 <b>repetitionPenalty</b> <i>。</i> 通过HTTP调用时，请将 <b>repetition_penalty </b>放入 <b>parameters</b> 对象中。</blockquote><blockquote>使用qwen-vl-plus_2025-01-25模型进行文字提取时，建议设置repetition_penalty为1.0。</blockquote><blockquote>不建议修改QVQ模型的默认 repetition_penalty 值。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><p><b>presence_penalty </b><code><i>float</i></code> （可选）</p><section><p>控制模型生成文本时的内容重复度。</p><p>取值范围：[-2.0, 2.0]。正值降低重复度，负值增加重复度。</p><p>在创意写作或头脑风暴等需要多样性、趣味性或创造力的场景中，建议调高该值；在技术文档或正式文本等强调一致性与术语准确性的场景中，建议调低该值。</p><p><span></span></p><p><b>presence_penalty默认值</b></p><p></p><p>Qwen3.5（非思考模式）、qwen3-max-preview（思考模式）、Qwen3（非思考模式）、Qwen3-Instruct系列、qwen3-0.6b/1.7b/4b（思考模式）、QVQ系列、qwen-max、qwen-max-latest、qwen-max-latest <span>、qwen-max-2024-09-19、</span> qwen2.5-vl系列、qwen-vl-max系列、qwen-vl-plus <span>、qwen2-vl-72b-instruct、qwen-vl-plus-2025-01-02</span> 、Qwen3-VL（非思考）：1.5；</p><p>qwen-vl-plus-latest、qwen-vl-plus-2025-08-15 <span>、qwen-vl-plus-2025-07-10</span> ：1.2</p><p>qwen-vl-plus-2025-01-25：1.0；</p><p>qwen3-8b/14b/32b/30b-a3b/235b-a22b（思考模式）、qwen-plus/qwen-plus-latest/2025-04-28（思考模式）、qwen-turbo/qwen-turbo/2025-04-28（思考模式）：0.5；</p><p>其余均为0.0。</p><p><span></span></p><p><b>原理介绍</b></p><p></p><p>如果参数值是正数，模型将对目前文本中已存在的Token施加一个惩罚值（惩罚值与文本出现的次数无关），减少这些Token重复出现的几率，从而减少内容重复度，增加用词多样性。</p><p><span></span></p><p><b>示例</b></p><p></p><p>提示词：把这句话翻译成中文“This movie is good. The plot is good, the acting is good, the music is good, and overall, the whole movie is just good. It is really good, in fact. The plot is so good, and the acting is so good, and the music is so good.”</p><p>参数值为2.0：这部电影很好。剧情很棒，演技棒，音乐也非常好听，总的来说，整部电影都好得不得了。实际上它真的很优秀。剧情非常精彩，演技出色，音乐也是那么的动听。</p><p>参数值为0.0：这部电影很好。剧情好，演技好，音乐也好，总的来说，整部电影都很好。事实上，它真的很棒。剧情非常好，演技也非常出色，音乐也同样优秀。</p><p>参数值为-2.0：这部电影很好。情节很好，演技很好，音乐也很好，总的来说，整部电影都很好。实际上，它真的很棒。情节非常好，演技也非常好，音乐也非常好。</p><blockquote>使用qwen-vl-plus-2025-01-25模型进行文字提取时，建议设置presence_penalty为1.5。</blockquote><blockquote>不建议修改QVQ模型的默认presence_penalty值。</blockquote></section><blockquote>Java SDK不支持设置该参数 <i>。</i> 通过HTTP调用时，请将 <b>presence_penalty </b>放入 <b>parameters</b> 对象中。</blockquote></td></tr><tr><td rowspan="1" colspan="1"><section><blockquote>Java SDK 为 <b>vlHighResolutionImages</b> （需要的最低版本为2.20.8 <b>）</b> <i>。</i> 通过HTTP调用时，请将 <b>vl_high_resolution_images </b>放入 <b>parameters</b> 对象中。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><p><b>vl_enable_image_hw_output </b><code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>是否返回图像缩放后的尺寸。模型会对输入的图像进行缩放处理，配置为 True 时会返回图像缩放后的高度和宽度，开启流式输出时，该信息在最后一个数据块（chunk）中返回。支持 <a href="https://help.aliyun.com/zh/model-studio/vision">Qwen-VL模型</a> 。</p><blockquote>Java SDK中为 <b>vlEnableImageHwOutput</b> ，Java SDK最低版本为2.20.8 <i>。</i> 通过HTTP调用时，请将 <b>vl_enable_image_hw_output </b>放入 <b>parameters</b> 对象中。</blockquote></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>max_tokens </b><code><i>integer</i></code> （可选）</p><section><p>用于限制模型输出的最大 Token 数。若生成内容超过此值，生成将提前停止，且返回的 <code>finish_reason</code> 为 <code>length</code> 。</p><p>默认值与最大值均为模型的最大输出长度，请参见 <a href="https://help.aliyun.com/zh/model-studio/models#9f8890ce29g5u">文本生成-千问</a> 。</p><p>适用于需控制输出长度的场景，如生成摘要、关键词，或用于降低成本、缩短响应时间。</p><p>触发 <code>max_tokens </code> 时，响应的 finish_reason 字段为 <code>length</code> 。</p><blockquote><code>max_tokens</code> 不限制思考模型思维链的长度。</blockquote></section><blockquote>Java SDK中为 <b>maxTokens</b> （模型为千问VL <span>/Audio</span> 时，Java SDK中为 <b>maxLength，</b> 在 2.18.4 版本之后支持也设置为 maxTokens） <i>。</i> 通过HTTP调用时，请将 <b>max_tokens </b>放入 <b>parameters</b> 对象中。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>seed </b><code><i>integer</i></code> （可选）</p><p>随机数种子。用于确保在相同输入和参数下生成结果可复现。若调用时传入相同的 <code>seed</code> 且其他参数不变，模型将尽可能返回相同结果。</p><p>取值范围： <code>[0,2<sup>31</sup>−1]</code> 。</p><p><span></span></p><p><b>seed默认值</b></p><p></p><p>qwen-vl-plus-2025-01-02、qwen-vl-max、qwen-vl-max-latest、qwen-vl-max-2025-04-08、qwen-vl-max-2025-04-02、qwen-vl-max-2024-12-30、qvq-72b-preview、qvq-max系列：3407；</p><p>qwen-vl-max-2025-01-25、qwen-vl-max-2024-11-19、qwen-vl-max-2024-02-01、qwen2-vl-72b-instruct、qwen2-vl-2b-instruct、qwen-vl-plus、qwen-vl-plus-latest、qwen-vl-plus-2025-05-07、qwen-vl-plus-2025-01-25：无默认值；</p><p>其余模型均为1234。</p><blockquote>通过HTTP调用时，请将 <b>seed </b>放入 <b>parameters</b> 对象中。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>incremental_output </b><code><i>boolean</i></code> （可选）默认为 <code>false</code> （Qwen3-Max、Qwen3-VL、 <a href="https://help.aliyun.com/zh/model-studio/models#9d516d17965af">Qwen3 开源版</a> 、 <a href="https://help.aliyun.com/zh/model-studio/deep-thinking">QwQ</a> 、 <a href="https://help.aliyun.com/zh/model-studio/visual-reasoning">QVQ</a> 模型默认值为 <code>true</code> ）</p><p>在流式输出模式下是否开启增量输出。推荐您优先设置为 <code>true</code> 。</p><p>参数值：</p><ul><li><p>false：每次输出为当前已经生成的整个序列，最后一次输出为生成的完整结果。</p><div><pre><code>I
I like
I like apple
I like apple.</code></pre></div></li><li><p>true（推荐）：增量输出，即后续输出内容不包含已输出的内容。您需要实时地逐个读取这些片段以获得完整的结果。</p><div><pre><code>I
like
apple
.</code></pre></div></li></ul><blockquote>Java SDK中为 <b>incrementalOutput</b> <i>。</i> 通过HTTP调用时，请将 <b>incremental_output </b>放入 <b>parameters</b> 对象中。</blockquote><blockquote>QwQ 模型与思考模式下的 Qwen3 模型只支持设置为 <code>true</code> 。由于 Qwen3 商业版模型默认值为 <code>false</code> ，您需要在思考模式下手动设置为 <code>true</code> 。</blockquote><blockquote>Qwen3 开源版模型不支持设置为 <code>false</code> 。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><p><b>response_format </b><code><i>object</i></code> （可选） 默认值为 <code>{"type": "text"}</code></p><p>返回内容的格式。可选值：</p><ul><li><p><code>{"type": "text"}</code> ：输出文字回复；</p></li><li><p><code>{"type": "json_object"}</code> ：输出标准格式的JSON字符串。</p></li><li><p><code>{"type": "json_schema","json_schema": {...}&nbsp;}</code> ：输出指定格式的JSON字符串。</p></li></ul><blockquote>相关文档： <a href="https://help.aliyun.com/zh/model-studio/qwen-structured-output">结构化输出</a> 。</blockquote><blockquote>支持的模型参见 <a href="https://help.aliyun.com/zh/model-studio/qwen-structured-output#7a8e438e89xeq">支持的模型</a> 。</blockquote><blockquote>若指定为 <code>{"type": "json_object"}</code> ，需在提示词中明确指示模型输出JSON，如：“请按照json格式输出”，否则会报错。</blockquote><blockquote>Java SDK中为responseFormat <i>。</i> 通过HTTP调用时，请将 <b>response_format </b>放入 <b>parameters</b> 对象中。</blockquote><p><span></span></p><p><b>属性</b></p><p></p><section><p><b>type </b><code><i>string</i></code> <b>（必选）</b></p><p>返回内容的格式。可选值：</p><ul><li><p><code>text</code> ：输出文字回复；</p></li><li><p><code>json_object</code> ：输出标准格式的JSON字符串；</p></li><li><p><code>json_schema</code> ：输出指定格式的JSON字符串。</p></li></ul></section><p><b>json_schema </b><code><i>object</i></code></p><p>当 type 为 json_schema 时，该字段为必选，用于定义结构化输出的配置。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>name </b><code><i>string</i></code> <b>（必选）</b></p><p>Schema 的唯一标识名称。仅支持字母（不区分大小写）、数字、下划线和短横线，最长 64 个字符。</p><p><b>description </b><code><i>string</i></code> （可选）</p><p>描述 Schema 的用途，帮助模型理解输出的语义上下文。</p><section><p><b>schema </b><code><i>object</i></code> （可选）</p><p>符合 JSON Schema 标准的对象，定义模型输出的数据结构。</p><blockquote>构建JSON Schema 方法参加： <a href="https://json-schema.org/">JSON Schema</a></blockquote></section><section><p><b>strict </b><code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>控制是否强制模型严格遵守 Schema 的所有约束。</p><ul><li><p><b>true（推荐）</b></p><p>模型严格遵循字段类型、必填项、格式等所有约束，确保输出 100% 合规。</p></li><li><p><b>false（不推荐）</b></p><p>模型仅大致遵循 Schema，可能生成不符合规范的输出，导致验证失败。</p></li></ul></section></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>result_format </b><code><i>string </i></code> （可选）默认为 <code>text</code> （Qwen3-Max、Qwen3-VL、 <a href="https://help.aliyun.com/zh/model-studio/deep-thinking">QwQ</a> 模型、Qwen3 开源模型（除了qwen3-next-80b-a3b-instruct） <span>与 Qwen-Long 模型</span> 默认值为 message）</p><p>返回数据的格式。推荐您优先设置为 <code>message</code> ，可以更方便地进行 <a href="https://help.aliyun.com/zh/model-studio/multi-round-conversation">多轮对话</a> 。</p><blockquote>平台后续将统一调整默认值为 <code>message</code> 。</blockquote><blockquote>Java SDK中为 <b>resultFormat</b> <i>。</i> 通过HTTP调用时，请将 <b>result_format </b>放入 <b>parameters</b> 对象中。</blockquote><blockquote>模型为千问VL/QVQ <span>/Audio</span> 时，设置 <code>text</code> 不生效。</blockquote><blockquote>Qwen3-Max、Qwen3-VL、思考模式下的 Qwen3 模型只能设置为 <span><code>message</code></span> ，由于 Qwen3 商业版模型默认值为 <code>text</code> ，您需要将其设置为 <span><code>message</code></span> 。</blockquote><blockquote>如果您使用 Java SDK 调用Qwen3 开源模型，并且传入了 <code>text</code> ，依然会以 <span><code>message</code></span> 格式进行返回。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><p><b>logprobs</b> <code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>是否返回输出 Token 的对数概率，可选值：</p><ul><li><p><code>true</code></p><p>返回</p></li><li><p><code>false</code></p><p>不返回</p></li></ul><p>支持以下模型：</p><ul><li><p>qwen-plus系列的快照模型（不包含稳定版模型）</p></li><li><p>qwen-turbo 系列的快照模型（不包含稳定版模型）</p></li><li><p>qwen3-vl-plus系列（包含稳定版模型）</p></li><li><p>qwen3-vl-flash系列（包含稳定版模型）</p></li><li><p>Qwen3 开源模型</p></li></ul><blockquote>通过HTTP调用时，请将 <b>logprobs </b>放入 <b>parameters</b> 对象中。</blockquote></td></tr><tr><td rowspan="1" colspan="1"><p><b>top_logprobs</b> <code><i>integer</i></code> （可选）默认值为0</p><p>指定在每一步生成时，返回模型最大概率的候选 Token 个数。</p><p>取值范围：[0,5]</p><p>仅当 <code>logprobs</code> 为 <code>true</code> 时生效。</p><blockquote>Java SDK中为 <b>topLogprobs</b> <i>。</i> 通过HTTP调用时，请将 <b>top_logprobs </b>放入 <b>parameters</b> 对象中。</blockquote></td></tr><tr><td rowspan="1" colspan="1"><p><b>n </b><code><i>integer</i></code> （可选） 默认值为1</p></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>stop </b><code><i>string 或 array </i></code> （可选）</p><section><p>用于指定停止词。当模型生成的文本中出现 <code>stop</code> &nbsp;指定的字符串或 <code>token_id</code> 时，生成将立即终止。</p><p>可传入敏感词以控制模型的输出。</p><blockquote>stop为数组时，不可将 <code>token_id</code> 和字符串同时作为元素输入，比如不可以指定为 <code>["你好",104307]</code> 。</blockquote></section><blockquote>通过HTTP调用时，请将 <b>stop </b>放入 <b>parameters</b> 对象中。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>tools </b><code><i>array</i></code> （可选）</p><p>包含一个或多个工具对象的数组，供模型在 Function Calling 中调用。相关文档： <a href="https://help.aliyun.com/zh/model-studio/qwen-function-calling">Function Calling</a></p><p>使用 <code>tools</code> 时，必须将 <code>result_format</code> 设为 <code>message</code> 。</p><p>发起 Function Calling，或提交工具执行结果时，都必须设置 <code>tools</code> 参数。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>type </b><code><i>string</i></code> <b>（必选）</b></p><p>工具类型，当前仅支持 <code>function</code> 。</p><p><b>function </b><code><i>object</i></code> <b>（必选）</b></p><blockquote>通过HTTP调用时，请将 <b>tools </b>放入 <b>parameters</b> 对象中。暂时不支持qwen-vl <span>与qwen-audio</span> 系列模型。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>tool_choice </b><code><i>string 或 object </i></code> （可选）默认值为 <code>auto</code></p><p>工具选择策略。若需对某类问题强制指定工具调用方式（例如始终使用某工具或禁用所有工具），可设置此参数。</p><ul><li><p><code>auto</code></p><p>大模型自主选择工具策略；</p></li><li><p><code>none</code></p><p>若在特定请求中希望临时禁用工具调用，可设定 <code>tool_choice</code> 参数为 <code>none</code> ；</p></li><li><p><code>{"type": "function", "function": {"name": "the_function_to_call"}}</code></p><p>若希望强制调用某个工具，可设定 <code>tool_choice</code> 参数为 <code>{"type": "function", "function": {"name": "the_function_to_call"}}</code> ，其中 <code>the_function_to_call</code> 是指定的工具函数名称。</p><blockquote>思考模式的模型不支持强制调用某个工具。</blockquote></li></ul><blockquote>Java SDK中为 <b>toolChoice</b> <i>。</i> 通过HTTP调用时，请将 <b>tool_choice </b>放入 <b>parameters</b> 对象中。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>parallel_tool_calls</b> <code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>是否开启并行工具调用。</p><p>可选值：</p><ul><li><p><code>true</code> ：开启</p></li><li><p><code>false</code> ：不开启。</p></li></ul><p>并行工具调用详情请参见： <a href="https://help.aliyun.com/zh/model-studio/qwen-function-calling#cb6b5c484bt4x">并行工具调用</a> 。</p><blockquote>Java SDK中为 <b>parallelToolCalls</b> <i>。</i> 通过HTTP调用时，请将 <b>parallel_tool_calls </b>放入 <b>parameters</b> 对象中。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>enable_search </b><code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>模型在生成文本时是否使用互联网搜索结果进行参考。取值如下：</p><ul><li><p>true：启用互联网搜索，模型会将搜索结果作为文本生成过程中的参考信息，但模型会基于其内部逻辑判断是否使用互联网搜索结果。</p><section><blockquote>若开启后未联网搜索，可优化提示词，或设置 <code>search_options</code> 中的 <code>forced_search</code> 参数开启强制搜索。</blockquote></section></li><li><p>false：关闭互联网搜索。</p></li></ul><p>计费信息请参见 <a href="https://help.aliyun.com/zh/model-studio/web-search#92ce83df3a599">计费说明</a> 。</p><blockquote>Java SDK中为 <b>enableSearch</b> <i>。</i> 通过HTTP调用时，请将 <b>enable_search </b>放入 <b>parameters</b> 对象中。</blockquote><blockquote>启用互联网搜索功能可能会增加 Token 的消耗。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>search_options </b><code><i>object</i></code> （可选）</p><p>联网搜索的策略。仅当 <code>enable_search</code> 为 <code>true</code> 时生效。详情参见 <a href="https://help.aliyun.com/zh/model-studio/web-search#cbddf5b28bug8">联网搜索</a> 。</p><blockquote>通过HTTP调用时，请将 <b>search_options </b>放入 <b>parameters</b> 对象中。Java SDK中为 <b>searchOptions</b> 。</blockquote><p><span></span></p><p><b>属性</b></p><p></p><section><p><b>enable_source </b><code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>在返回结果中是否展示搜索到的信息。参数值：</p><ul><li><p>true：展示；</p></li><li><p>false：不展示。</p></li></ul></section><section><p><b>enable_citation</b> <code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>是否开启[1]或[ref_1]样式的角标标注功能。在 <code>enable_source</code> 为 <code>true</code> 时生效。参数值：</p><ul><li><p>true：开启；</p></li><li><p>false：不开启。</p></li></ul></section><section><p><b>citation_format</b> <code><i>string</i></code> （可选）默认值为 <code>"[&lt;number&gt;]"</code></p><p>角标样式。在 <code>enable_citation</code> 为 <code>true</code> 时生效。参数值：</p><ul><li><p>[&lt;number&gt;]：角标形式为 <code>[1]</code> ；</p></li><li><p>[ref_&lt;number&gt;]：角标形式为 <code>[ref_1]</code> 。</p></li></ul></section><section><p><b>forced_search</b> <code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>是否强制开启搜索。参数值：</p><ul><li><p>true：强制开启；</p></li><li><p>false：不强制开启。</p></li></ul></section><p><b>search_strategy</b> <code><i>string</i></code> （可选）默认值为 <code>turbo</code></p><p>搜索互联网信息的策略。</p><p>可选值：</p><section><ul><li><p><code>turbo</code> （默认）: 兼顾响应速度与搜索效果，适用于大多数场景。</p></li><li><p><code>max</code>: 采用更全面的搜索策略，可调用多源搜索引擎，以获取更详尽的搜索结果，但响应时间可能更长。</p></li><li><p><code>agent</code> ：可多次调用联网搜索工具与大模型，实现多轮信息检索与内容整合。</p><blockquote>该策略仅适用于 qwen3.5-plus、qwen3.5-plus-2026-02-15、qwen3-max与 qwen3-max-2026-01-23 的思考模式（仅支持流式）、qwen3-max-2026-01-23的非思考模式、qwen3-max-2025-09-23。</blockquote><blockquote>启用该策略时，仅支持 <b>返回搜索来源</b> （ <code>enable_source: true</code> ），其他联网搜索功能不可用。</blockquote></li><li><p><code>agent_max</code> ：在 <code>agent</code> 策略基础上支持网页抓取，参见： <a href="https://help.aliyun.com/zh/model-studio/web-extractor">网页抓取</a> 。</p><blockquote>该策略仅适用于qwen3.5-plus、qwen3.5-plus-2026-02-15，以及 qwen3-max与 qwen3-max-2026-01-23 的思考模式。</blockquote><blockquote>启用该策略时，仅支持 <b>返回搜索来源</b> （ <code>enable_source: true</code> ），其他联网搜索功能不可用。</blockquote></li></ul></section><p><b>enable_search_extension</b> <code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>是否开启特定领域增强。参数值：</p><section><ul><li><p><code>true</code></p><p>开启。</p></li><li><p><code>false</code> （默认值）</p><p>不开启。</p></li></ul></section><section><p><b>prepend_search_result</b> <code><i>boolean</i></code> （可选）默认值为 <code>false</code></p><p>在流式输出且 <code>enable_source</code> 为 <code>true</code> 时，可通过 <code>prepend_search_result</code> 配置 <b>第一个返回的数据包</b> 是否只包含搜索来源信息。可选值：</p><ul><li><p><code>true</code></p><p>只包含搜索来源信息。</p></li><li><p><code>false</code> （默认值）</p><p>包含搜索来源信息与大模型回复信息。</p></li></ul><blockquote>暂不支持 DashScope Java SDK。</blockquote></section></section></td></tr><tr><td rowspan="1" colspan="1"></td></tr></tbody></table>

<table><tbody><tr><td rowspan="1" colspan="1"><h2>chat响应对象（流式与非流式输出格式一致）</h2></td><td rowspan="6" colspan="1"><div><pre><code>{
  "status_code": 200,
  "request_id": "902fee3b-f7f0-9a8c-96a1-6b4ea25af114",
  "code": "",
  "message": "",
  "output": {
    "text": null,
    "finish_reason": null,
    "choices": [
      {
        "finish_reason": "stop",
        "message": {
          "role": "assistant",
          "content": "我是阿里云开发的一款超大规模语言模型，我叫千问。"
        }
      }
    ]
  },
  "usage": {
    "input_tokens": 22,
    "output_tokens": 17,
    "total_tokens": 39
  }
}</code></pre></div></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>status_code </b><code><i>string</i></code></p><p>本次请求的状态码。200 表示请求成功，否则表示请求失败。</p><blockquote>Java SDK不会返回该参数。调用失败会抛出异常，异常信息为 <b>status_code</b> 和 <b>message</b> 的内容。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>request_id </b><code><i>string</i></code></p><p>本次调用的唯一标识符。</p><blockquote>Java SDK返回参数为 <b>requestId。</b></blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><section><p><b>code </b><code><i>string</i></code></p><p>错误码，调用成功时为空值。</p><blockquote>只有Python SDK返回该参数。</blockquote></section></td></tr><tr><td rowspan="1" colspan="1"><p><b>output </b><code><i>object</i></code></p><p>调用结果信息。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>text </b><code><i>string</i></code></p><p>模型生成的回复。当设置输入参数 <b>result_format</b> 为 <b>text</b> 时将回复内容返回到该字段。</p><section><p><b>finish_reason </b><code><i>string</i></code></p><p>当设置输入参数 <b>result_format</b> 为 <b>text</b> 时该参数不为空。</p><p>有四种情况：</p><ul><li><p>正在生成时为null；</p></li><li><p>因模型输出自然结束，或触发输入参数中的stop条件而结束时为stop；</p></li><li><p>因生成长度过长而结束为length；</p></li><li><p>因发生工具调用为tool_calls。</p></li></ul></section><p><b>choices </b><code><i>array</i></code></p><p>模型的输出信息。当result_format为message时返回choices参数。</p><p><span></span></p><p><b>属性</b></p><p></p><section><p><b>finish_reason </b><code><i>string</i></code></p><p>有四种情况：</p><ul><li><p>正在生成时为null；</p></li><li><p>因模型输出自然结束，或触发输入参数中的stop条件而结束时为stop；</p></li><li><p>因生成长度过长而结束为length；</p></li><li><p>因发生工具调用为tool_calls。</p></li></ul></section><p><b>message </b><code><i>object</i></code></p><p>模型输出的消息对象。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>role </b><code><i>string</i></code></p><p>输出消息的角色，固定为assistant。</p><section><p><b>content </b><code><i>string或array</i></code></p><p>输出消息的内容。当使用qwen-vl或qwen-audio系列模型时为 <code>array</code> ，其余情况为 <code>string</code> 。</p><blockquote>如果发起Function Calling，则该值为空。</blockquote></section><p><b>reasoning_content</b> <code><i>string</i></code></p><p>模型的深度思考内容。</p><p><b>tool_calls </b><code><i>array</i></code></p><p>若模型需要调用工具，则会生成tool_calls参数。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>function </b><code>object</code></p><p>调用工具的名称，以及输入参数。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>name </b><code><i>string</i></code></p><p>调用工具的名称</p><section><p><b>arguments </b><code><i>string</i></code></p><p>需要输入到工具中的参数，为JSON字符串。</p><blockquote>由于大模型响应有一定随机性，输出的JSON字符串并不总满足于您的函数，建议您在将参数输入函数前进行参数的有效性校验。</blockquote></section><p><b>index</b> <code><i>integer</i></code></p><p>当前 <b>tool_calls</b> 对象在tool_calls数组中的索引。</p><p><b>id</b> <code><i>string</i></code></p><p>本次工具响应的ID。</p><p><b>type</b> <code><i>string</i></code></p><p>工具类型，固定为 <code>function</code> 。</p><p><b>logprobs </b><code><i>object</i></code></p><p>当前 choices 对象的概率信息。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>content</b> <code><i>array</i></code></p><p>带有对数概率信息的 Token 数组。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>token</b> <code><i>string</i></code></p><p>当前 Token。</p><p><b>bytes</b> <code><i>array</i></code></p><p>当前 Token 的 UTF‑8 原始字节列表，用于精确还原输出内容，在处理表情符号、中文字符时有帮助。</p><p><b>logprob</b> <code><i>float</i></code></p><p>当前 Token 的对数概率。返回值为 null 表示概率值极低。</p><p><b>top_logprobs</b> <code><i>array</i></code></p><p>当前 Token 位置最可能的若干个 Token 及其对数概率，元素个数与入参的 <code>top_logprobs</code> 保持一致。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>token</b> <code><i>string</i></code></p><p>当前 Token。</p><p><b>logprob</b> <code><i>float</i></code></p><p>当前 Token 的对数概率。返回值为 null 表示概率值极低。</p><p><b>search_info </b><code><i>object</i></code></p><p>联网搜索到的信息，在设置 <code>search_options</code> 参数后会返回该参数。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>search_results </b><code><i>array</i></code></p><p>联网搜索到的结果。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>site_name </b><code><i>string</i></code></p><p>搜索结果来源的网站名称。</p><p><b>icon </b><code><i>string</i></code></p><p>来源网站的图标URL，如果没有图标则为空字符串。</p><p><b>index </b><code><i>integer</i></code></p><p>搜索结果的序号，表示该搜索结果在 <code>search_results</code> 中的索引。</p><p><b>title </b><code><i>string</i></code></p><p>搜索结果的标题。</p><p><b>url </b><code><i>string</i></code></p><p>搜索结果的链接地址。</p><p><b>extra_tool_info </b><code><i>array</i></code></p><p>开启 <code>enable_search_extension</code> 参数后返回的领域增强信息。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>result </b><code><i>string</i></code></p><p>领域增强工具输出信息。</p><p><b>tool </b><code><i>string</i></code></p><p>领域增强使用的工具。</p></td></tr><tr><td rowspan="1" colspan="1"><p><b>usage </b><code><i>map</i></code></p><p>本次chat请求使用的Token信息。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>input_tokens</b> <code><i>integer</i></code></p><p>用户输入内容转换成Token后的长度。</p><p><b>output_tokens</b> <code><i>integer</i></code></p><p>模型输出内容转换成Token后的长度。</p><p><b>input_tokens_details</b> <code><i>integer</i></code></p><p>使用 <a href="https://help.aliyun.com/zh/model-studio/vision">Qwen-VL 模型</a> 或 <a href="https://help.aliyun.com/zh/model-studio/visual-reasoning">QVQ模型</a> 时，输入内容转换成Token后的长度详情。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>image_tokens</b> <code><i>integer</i></code></p><p>输入的图像转换为Token后的长度。</p><p><b>video_tokens</b> <code><i>integer</i></code></p><p>输入的视频文件或图像列表转换为Token后的长度。</p><p><b>total_tokens</b> <code><i>integer</i></code></p><p>当输入为纯文本时返回该字段，为 <b>input_tokens</b> 与 <b>output_tokens</b> 之和 <b>。</b></p><p><b>image_tokens</b> <code><i>integer</i></code></p><p>输入内容包含 <code>image</code> 时返回该字段。为用户输入图片内容转换成Token后的长度。</p><p><b>video_tokens</b> <code><i>integer</i></code></p><p>输入内容包含 <code>video</code> 时返回该字段。为用户输入视频内容转换成Token后的长度。</p><p><b>audio_tokens</b> <code><i>integer</i></code></p><p>输入内容包含 <code>audio</code> 时返回该字段。为用户输入音频内容转换成Token后的长度。</p><p><b>output_tokens_details</b> <code><i>integer</i></code></p><p>输出内容转换成 Token后的长度详情。</p><p><span></span></p><p><b>属性</b></p><p></p><p><b>text_tokens</b> <code><i>integer</i></code></p><p>输出的文本转换为Token后的长度。</p><p><b>reasoning_tokens</b> <code><i>integer</i></code></p><p>思考过程转换为Token后的长度。</p><p><b>prompt_tokens_details</b> <code><i>object</i></code></p><p>输入 Token 的细粒度分类。</p></td></tr></tbody></table>

## 错误码

如果模型调用失败并返回报错信息，请参见 [错误信息](https://help.aliyun.com/zh/model-studio/error-code) 进行解决。

- 本页导读 （1）

- 请求体

- chat响应对象（流式与非流式输出格式一致）

- 错误码

[![](https://img.alicdn.com/imgextra/i2/O1CN018yfMwK1O05LxJScxL_!!6000000001642-2-tps-144-464.png)](https://smartservice.console.aliyun.com/service/pre-sales-chat?iframe=true&channelCode=floating-widgets&topicCode=sales-im&topicServiceId=1)

点击开启售前

在线咨询服务



千问Plus
能力均衡，推理效果、成本和速度介于千问Max和千问Flash之间，适合中等复杂任务。使用方法｜思考模式｜API参考｜在线体验

Qwen3.5 Plus 支持文本、图像和视频输入。在纯文本任务上的效果可媲美 Qwen3 Max，性能更优且成本更低。在多模态能力上，相比 Qwen3 VL 系列有显著提升。
中国内地全球国际美国金融云
在中国内地部署模式下，接入点与数据存储均位于北京地域，模型推理计算资源仅限于中国内地。

模型名称

版本

模式

上下文长度

最大输入

最长思维链

最大输出

输入成本

输出成本

思维链+输出
免费额度

（注）

（Token数）

（每百万Token）

qwen3.5-plus

默认开启思考模式
稳定版

思考

1,000,000

983,616

81,920

65,536

阶梯计价，请参见表格下方说明。

各100万Token

有效期：百炼开通后90天内

非思考

991,808

-