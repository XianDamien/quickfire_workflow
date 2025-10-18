import os
import sys
import dashscope

if len(sys.argv) != 2:
    print("用法: python3 captioner_qwen3.py <audio_file_path>")
    print("示例: python3 captioner_qwen3.py ../audio/sample.mp3")
    exit(-1)

# 获取命令行参数中的音频文件路径
audio_path = sys.argv[1]

# 添加 file:// 前缀以支持多模态输入
if not audio_path.startswith("file://"):
    audio_file_path = f"file://{audio_path}"
else:
    audio_file_path = audio_path

messages = [
    {
        "role": "user",
        "content": [{"audio": audio_file_path}],
    }
]

response = dashscope.MultiModalConversation.call(
            model="qwen3-omni-30b-a3b-captioner",
            messages=messages)

print("输出结果为：")
print(response["output"]["choices"][0]["message"].content[0]["text"])
