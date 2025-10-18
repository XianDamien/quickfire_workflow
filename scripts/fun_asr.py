from http import HTTPStatus
from dashscope.audio.asr import Transcription
import dashscope
import os
import json
import sys

# 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "sk-xxx"
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
audio_filepath = sys.argv[1]

transcribe_response = Transcription.async_call(
    model='fun-asr',
    file_urls=[f"file://{audio_filepath}"]              
)

while True:
    if transcribe_response.output.task_status == 'SUCCEEDED' or transcribe_response.output.task_status == 'FAILED':
        break
    transcribe_response = Transcription.fetch(task=transcribe_response.output.task_id)

if transcribe_response.status_code == HTTPStatus.OK:
    print(json.dumps(transcribe_response.output, indent=4, ensure_ascii=False))
    print('transcription done!')
