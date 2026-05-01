"""AI 模型调用封装 — DeepSeek V4 (Anthropic 兼容端点) + 重试/结构化输出。"""
import os
import json
import time
import logging
from typing import Any, Dict, List, Optional, Type
from pathlib import Path

import anthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"


def _load_settings():
    import yaml
    with open(SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def _get_model_config(model_key=None) -> dict:
    """Get model config by key (index, name, role, or None=first).

    model_key:
        None/int  → models[N] (default models[0])
        "opus"     → match by name field (substring)
        "fast"     → match by role field
    """
    settings = _load_settings()
    models = settings.get("model", [])
    if not models:
        raise RuntimeError("No model configured in config/settings.yaml")

    if model_key is None:
        return models[0]

    if isinstance(model_key, int):
        if model_key < len(models):
            return models[model_key]
        raise RuntimeError(f"Model index {model_key} out of range (total {len(models)})")

    # string: match by name or role
    for m in models:
        if model_key.lower() in m.get("name", "").lower():
            return m
        if model_key.lower() == m.get("role", "").lower():
            return m

    # fallback: first model
    logger.warning("Model '%s' not found, falling back to default", model_key)
    return models[0]


def _get_client(model_key=None) -> anthropic.Anthropic:
    cfg = _get_model_config(model_key)
    api_key = cfg.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("API Key not found. Configure model.api_key in settings.yaml or set ANTHROPIC_API_KEY env var")
    base_url = cfg.get("base_url_anthropic", "https://api.deepseek.com/anthropic")
    timeout = cfg.get("timeout", 300)
    return anthropic.Anthropic(api_key=api_key, base_url=base_url, timeout=timeout)


def _get_model_name(model_key=None) -> str:
    return _get_model_config(model_key).get("model", "deepseek-v4-pro")


def _get_max_retries(model_key=None) -> int:
    return _get_model_config(model_key).get("max_retries", 3)


def _get_text_from_response(response) -> str:
    """从响应中提取文本，跳过 ThinkingBlock。"""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    raise ValueError("No TextBlock found in response")


def chat(
    system: str,
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    model_key=None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    use_cache: bool = True,
) -> str:
    """
    发送单次对话请求，返回文本响应。
    自动重试。DeepSeek Anthropic 端点不支持 prompt caching，use_cache 参数忽略。

    model_key: select by index, name, or role (e.g. 0, "opus", "fast")
    """
    client = _get_client(model_key)
    model = model or _get_model_name(model_key)
    max_retries = _get_max_retries(model_key)

    api_kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": messages,
    }

    for attempt in range(max_retries):
        try:
            response = client.messages.create(**api_kwargs)
            logger.info(
                "API call success | model=%s | input_tokens=%s | output_tokens=%s",
                model,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
            return _get_text_from_response(response)
        except Exception as e:
            wait = 2 ** attempt
            logger.warning("API call failed (attempt %d/%d): %s, retry in %ds", attempt + 1, max_retries, e, wait)
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                raise


def chat_structured(
    system: str,
    prompt: str,
    output_schema: Type[BaseModel],
    model: Optional[str] = None,
    model_key=None,
    temperature: float = 0.1,
    normalizer=None,
) -> BaseModel:
    """
    发送消息并获取结构化 JSON 输出。
    model_key: select by index, name, or role (e.g. 0, "opus", "fast")
    normalizer: optional callback to fix raw JSON dict before Pydantic validation
    """
    import json
    client = _get_client(model_key)
    model = model or _get_model_name(model_key)
    max_retries = _get_max_retries(model_key)

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = _get_text_from_response(response)
            json_str = _extract_json(text)

            # Apply normalizer to fix common LLM output format issues
            if normalizer:
                try:
                    raw = json.loads(json_str)
                    raw = normalizer(raw)
                    json_str = json.dumps(raw, ensure_ascii=False)
                except json.JSONDecodeError:
                    pass  # If parsing fails, let Pydantic report the error

            logger.info(
                "Structured output success | model=%s | tokens=%s",
                model, response.usage.output_tokens,
            )
            return output_schema.model_validate_json(json_str)
        except Exception as e:
            wait = 2 ** attempt
            logger.warning("Structured output failed (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                raise


def _extract_json(text: str) -> str:
    """从文本中提取 JSON 块。处理 ```json ... ``` 包裹的情况。"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def chat_safe(system: str, messages: list, model: str = None, model_key=None, max_tokens: int = 4096, temperature: float = 0.3) -> str:
    """安全调用 chat()，失败时返回错误信息文本而非抛出异常。"""
    try:
        return chat(system, messages, model=model, model_key=model_key, max_tokens=max_tokens, temperature=temperature)
    except Exception as e:
        logger.error("LLM call ultimately failed: %s", e)
        return f"\n\n> [报告生成失败: {e}]"


def count_tokens_estimate(text: str) -> int:
    """粗略估算 token 数（中文约1.5字符/token，英文约4字符/token）。"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)
