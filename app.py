import os
from flask import Flask, request, jsonify
from hugchat import hugchat
from hugchat.login import Login
import time
import uuid

app = Flask(__name__)

# 从环境变量获取账号信息
EMAIL = os.environ.get('HUGCHAT_EMAIL')
PASSWORD = os.environ.get('HUGCHAT_PASSWORD')

# 初始化chatbot
sign = Login(EMAIL, PASSWORD)
cookies = sign.login()
chatbot = hugchat.ChatBot(cookies=cookies.get_dict())

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    data = request.json
    
    # 检查是否启用联网搜索
    web_search = 'internet' in data['model'].lower()
    
    # 构造消息
    messages = data['messages']
    last_message = messages[-1]['content']
    
    # 调用hugging-chat-api
    try:
        response = chatbot.query(last_message, web_search=web_search)
        
        # 构造OpenAI格式的响应
        openai_response = {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": data['model'],
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.text if isinstance(response, hugchat.ChatMessage) else response
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
        
        # 如果启用了联网搜索，添加源信息
        if web_search and isinstance(response, hugchat.ChatMessage) and response.web_search_sources:
            openai_response["sources"] = [
                {"link": source.link, "title": source.title, "hostname": source.hostname}
                for source in response.web_search_sources
            ]
        
        return jsonify(openai_response)
    
    except Exception as e:
        return jsonify({
            "error": {
                "message": str(e),
                "type": "internal_error",
                "param": None,
                "code": None
            }
        }), 500

@app.route('/v1/models', methods=['GET'])
def list_models():
    try:
        models = chatbot.get_available_llm_models()
        
        return jsonify({
            "object": "list",
            "data": [
                {"id": model, "object": "model", "created": int(time.time()), "owned_by": "huggingface"}
                for model in models
            ] + [
                {"id": f"{model}-internet", "object": "model", "created": int(time.time()), "owned_by": "huggingface"}
                for model in models
            ]
        })
    
    except Exception as e:
        return jsonify({
            "error": {
                "message": str(e),
                "type": "internal_error",
                "param": None,
                "code": None
            }
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
