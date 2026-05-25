import requests
import json
import sys
import base64
import os
import re
from dataclasses import dataclass
from typing import Optional, List, Any
from PIL import Image
import io


@dataclass
class DeploymentConfig:
    """
    Configuration container for LLM deployment endpoints.
    
    Supports multiple deployment configurations (local vs remote, different model providers)
    to be easily swapped in.
    """
    url: str
    model_name: str
    api_key: Optional[str] = None
    max_tokens: int = 8192
    temperature: float = 0.6
    stream_timeout: int = 600
    
    def get_headers(self) -> dict:
        """Returns headers dict with API key if configured."""
        headers = {}
        if self.api_key:
            headers['Authorization'] = f"Bearer {self.api_key}"
        return headers


# Deployment configurations for different environments
DEPLOYMENT_CONFIGS = {
    "local": DeploymentConfig(
        url="http://127.0.0.1:8082/v1/chat/completions",
        model_name="Qwen3.5-35B-A3B-UD-IQ2_XXS",
        max_tokens=8192,
        temperature=0.6
    ),
    "remote": DeploymentConfig(
        url="https://api.example.com/v1/chat/completions",
        model_name="gpt-4-turbo",
        api_key="your-api-key-here",
        max_tokens=4096,
        temperature=0.7
    ),
    "default": DeploymentConfig(
        url="http://127.0.0.1:8082/v1/chat/completions",
        model_name="Qwen3.5-35B-A3B-UD-IQ2_XXS",
        max_tokens=8192,
        temperature=0.6
    )
}

# Current active deployment (can be swapped at runtime)
ACTIVE_DEPLOYMENT = "default"


def get_config() -> DeploymentConfig:
    """Returns the currently active deployment configuration."""
    return DEPLOYMENT_CONFIGS.get(ACTIVE_DEPLOYMENT, DEPLOYMENT_CONFIGS["default"])


def set_deployment(deployment_name: str):
    """Sets the active deployment configuration."""
    global ACTIVE_DEPLOYMENT
    if deployment_name in DEPLOYMENT_CONFIGS:
        ACTIVE_DEPLOYMENT = deployment_name
    else:
        raise ValueError(f"Unknown deployment: {deployment_name}")


def encode_image(image_path):
    """Downscales image to max 1280px before encoding to save VRAM."""
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((1280, 1280))
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            # OpenAI spec requires the data URI prefix
            base64_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            return f"data:image/jpeg;base64,{base64_str}"
    except Exception as e:
        print(f"Image processing error: {e}")
        return None


def _build_messages(prompt, system_message, messages_override, image_path):
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})

    if messages_override:
        messages.extend(list(messages_override))
        
    if prompt or image_path:
        content = []
        if prompt:
            content.append({"type": "text", "text": prompt})
        if image_path and os.path.exists(image_path):
            img_data = encode_image(image_path)
            if img_data:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": img_data}
                })
        if content:
            if len(content) == 1 and content[0]["type"] == "text":
                messages.append({"role": "user", "content": prompt})
            else:
                messages.append({"role": "user", "content": content})
                
    # Parse [ATTACHED_IMAGE: ...] dynamically in all messages
    processed_messages = []
    for msg in messages:
        if isinstance(msg.get("content"), str):
            text = msg["content"]
            
            # Strip reasoning tags from assistant history for Gemma 4
            if msg.get("role") == "assistant":
                text = re.sub(r'<\|channel>thought.*?(?:<\|channel>|$)', '', text, flags=re.DOTALL)
                text = re.sub(r'\[\[.*?\]\]', '', text, flags=re.DOTALL)
                text = text.strip()

            m = re.search(r'\[ATTACHED_IMAGE:\s*(.*?)\s*\]', text)
            if m:
                img_path = m.group(1).strip()
                img_data = None
                if os.path.exists(img_path):
                    img_data = encode_image(img_path)
                
                if img_data:
                    content = []
                    content.append({"type": "text", "text": text})
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": img_data}
                    })
                    processed_messages.append({"role": msg["role"], "content": content})
                else:
                    processed_messages.append(msg)
            else:
                processed_messages.append(msg)
        else:
            processed_messages.append(msg)
            
    return processed_messages


def query_llm(prompt, system_message=None, model_override=None, messages_override=None, image_path=None, max_tokens=None, config=None):
    """
    Query the LLM using the current deployment configuration.
    
    Args:
        prompt: The user prompt
        system_message: Optional system message
        model_override: Override the model name (takes precedence over deployment config)
        messages_override: Override the messages list
        image_path: Optional image path for multimodal input
        max_tokens: Override max tokens (uses deployment config default if None)
        config: Optional DeploymentConfig to use directly (bypasses global config)
    """
    cfg = config if config is not None else get_config()
    
    payload = {
        "model": model_override or config.model_name,
        "messages": _build_messages(prompt, system_message, messages_override, image_path),
        "stream": False,
        "max_tokens": max_tokens if max_tokens is not None else config.max_tokens,
        "temperature": config.temperature
    }

    headers = config.get_headers()
    
    try:
        res = requests.post(
            config.url, 
            json=payload, 
            headers=headers,
            timeout=config.stream_timeout
        )
        res.raise_for_status()
        
        message = res.json()['choices'][0]['message']
        content = message.get('content', '')
        reasoning = message.get('reasoning_content', '')
        
        if reasoning:
            # We wrap the reasoning in a think tag so the downstream logic knows what it is, 
            # or just return the content if we only want the final answer. 
            # For debugging and full context, combining them is often best.
            return f"\[\[\n{reasoning}\n\]\]\n{content}"
            
        return content
    except Exception as e:
        return f"Error connecting to Unified LLM: {e}"


def stream_llm(prompt, system_message=None, model_override=None, messages_override=None, image_path=None, config=None):
    """
    Stream responses from the LLM using the current deployment configuration.
    
    Args:
        prompt: The user prompt
        system_message: Optional system message
        model_override: Override the model name (takes precedence over deployment config)
        messages_override: Override the messages list
        image_path: Optional image path for multimodal input
        config: Optional DeploymentConfig to use directly (bypasses global config)
    """
    cfg = config if config is not None else get_config()
    
    payload = {
        "model": model_override or config.model_name,
        "messages": _build_messages(prompt, system_message, messages_override, image_path),
        "stream": True,
        "max_tokens": 2048,
        "temperature": config.temperature,
        "repeat_penalty": 1.15
    }

    headers = config.get_headers()
    
    try:
        with requests.post(
            config.url, 
            json=payload, 
            stream=True, 
            headers=headers,
            timeout=600
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        data_str = decoded_line[6:]
                        if data_str.strip() == '[DONE]':
                            break
                        try:
                            data = json.loads(data_str)
                            if len(data.get('choices', [])) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta and delta['content'] is not None:
                                    yield delta['content']
                        except json.JSONDecodeError:
                            pass
    except Exception as e:
        yield f"Error connecting to Unified LLM stream: {e}"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(query_llm(" ".join(sys.argv[1:])))
