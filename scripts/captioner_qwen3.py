import os
import sys
import dashscope


def transcribe_audio(audio_path, api_key=None, model="qwen3-omni-30b-a3b-captioner"):
    """
    将音频文件转写为文本（ASR）

    Args:
        audio_path (str): 音频文件路径
        api_key (str, optional): DashScope API密钥，默认从环境变量读取
        model (str, optional): 使用的多模态模型，默认 "qwen3-omni-30b-a3b-captioner"

    Returns:
        str: ASR转写结果（文本格式）
    """
    if api_key is None:
        api_key = os.getenv('DASHSCOPE_API_KEY')

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
        api_key=api_key,
        model=model,
        messages=messages
    )

    return response["output"]["choices"][0]["message"].content[0]["text"]


# ===== 主程序入口（向后兼容）=====
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python3 captioner_qwen3.py <audio_file_path>")
        print("示例: python3 captioner_qwen3.py ../audio/sample.mp3")
        exit(-1)

    # 获取命令行参数中的音频文件路径
    audio_path = sys.argv[1]

    # 调用转写函数
    result = transcribe_audio(audio_path)

    print("输出结果为：")
    print(result)
