通过纯文本传入信息
除了通过 file-id 传入文档信息外，您还可以直接使用字符串传入文档内容。在此方法下，为避免模型混淆角色设定与文档内容，请确保在 messages 的第一条消息中添加用于角色设定的信息。

受限于API调用请求体大小，如果您的文本内容长度超过100万Token，请通过文件ID传入信息对话。
简单示例传入多文档追加文档
您可以直接将文档内容输入System Message中。

PythonJavacurl
 
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),  # 如果您没有配置环境变量，请在此处替换您的API-KEY
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 填写DashScope服务base_url
)
# 初始化messages列表
completion = client.chat.completions.create(
    model="qwen-long",
    messages=[
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'system', 'content': '阿里云百炼手机产品介绍 阿里云百炼X1 ——————畅享极致视界：搭载6.7英寸1440 x 3200像素超清屏幕...'},
        {'role': 'user', 'content': '文章讲了什么？'}
    ],
    # 所有代码示例均采用流式输出，以清晰和直观地展示模型输出过程。如果您希望查看非流式输出的案例，请参见https://help.aliyun.com/zh/model-studio/text-generation
    stream=True,
    stream_options={"include_usage": True}
)

full_content = ""
for chunk in completion:
    if chunk.choices and chunk.choices[0].delta.content:
        # 拼接输出内容
        full_content += chunk.choices[0].delta.content
        print(chunk.model_dump())

print(full_content)