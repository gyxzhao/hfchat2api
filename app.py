import os
from flask import Flask, request, jsonify, Response, stream_with_context
from hugchat import hugchat
from hugchat.login import Login
import time
import uuid
from functools import wraps
import json

app = Flask(__name__)

# Get account information and API key from environment variables
EMAIL = os.environ.get('HUGCHAT_EMAIL')
PASSWORD = os.environ.get('HUGCHAT_PASSWORD')
AUTH_KEY = os.environ.get('AUTH_KEY')

# Initialize chatbot
sign = Login(EMAIL, PASSWORD)
cookies = sign.login()
chatbot = hugchat.ChatBot(cookies=cookies.get_dict())

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                auth_type, auth_token = auth_header.split(None, 1)
                if auth_type.lower() == 'bearer' and auth_token == AUTH_KEY:
                    return f(*args, **kwargs)
            except ValueError:
                pass
        return jsonify({"error": "Invalid or missing API key"}), 401
    return decorated

@app.route('/v1/chat/completions', methods=['POST'])
@require_auth
def chat_completions():
    data = request.json
    
    # Check if web search is enabled
    web_search = 'internet' in data['model'].lower()
    
    # Check if streaming is requested
    stream = data.get('stream', False)
    
    # Construct messages
    messages = data['messages']
    last_message = messages[-1]['content']
    
    # Call hugging-chat-api
    try:
        if stream:
            return Response(stream_with_context(stream_response(last_message, data['model'])), 
                            content_type='text/event-stream')
        else:
            return non_stream_response(last_message, data['model'])
    
    except Exception as e:
        return jsonify({
            "error": {
                "message": str(e),
                "type": "internal_error",
                "param": None,
                "code": None
            }
        }), 500

def stream_response(message, model):
    for response in chatbot.query(message, stream=True):
        chunk = {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": response
                },
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    
    # Send the final chunk
    final_chunk = {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop"
        }]
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"

def non_stream_response(message, model):
    response = chatbot.query(message)
    
    openai_response = {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
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
    
    return jsonify(openai_response)

@app.route('/v1/models', methods=['GET'])
@require_auth
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
