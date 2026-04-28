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


def _get_model_config() -> dict:
    """获取第一个模型配置。"""
    settings = _load_settings()
    models = settings.get("model", [])
    if not models:
        raise RuntimeError("config/settings.yaml 中未配置 model")
    return models[0]


def _get_client() -> anthropic.Anthropic:
    cfg = _get_model_config()
    api_key = cfg.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("未找到 API Key，请在 settings.yaml 的 model.api_key 中配置")
    base_url = cfg.get("base_url_anthropic", "https://api.deepseek.com/anthropic")
    timeout = cfg.get("timeout", 300)
    return anthropic.Anthropic(api_key=api_key, base_url=base_url, timeout=timeout)


def _get_model_name() -> str:
    return _get_model_config().get("model", "deepseek-v4-pro")


def _get_max_retries() -> int:
    return _get_model_config().get("max_retries", 3)


def _get_text_from_response(response) -> str:
    """从响应中提取文本，跳过 ThinkingBlock。"""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    raise ValueError("响应中没有找到 TextBlock")


def chat(
    system: str,
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    use_cache: bool = True,
) -> str:
    """
    发送单次对话请求，返回文本响应。
    自动重试。DeepSeek Anthropic 端点不支持 prompt caching，use_cache 参数忽略。
    """
    client = _get_client()
    model = model or _get_model_name()
    max_retries = _get_max_retries()

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
                "API 调用成功 | model=%s | input_tokens=%s | output_tokens=%s",
                model,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
            return _get_text_from_response(response)
        except Exception as e:
            wait = 2 ** attempt
            logger.warning("API 调用失败 (attempt %d/%d): %s，%ds 后重试", attempt + 1, max_retries, e, wait)
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                raise


def chat_structured(
    system: str,
    prompt: str,
    output_schema: Type[BaseModel],
    model: Optional[str] = None,
    temperature: float = 0.1,
) -> BaseModel:
    """
    发送消息并获取结构化 JSON 输出。
    """
    client = _get_client()
    model = model or _get_model_name()
    max_retries = _get_max_retries()

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
            logger.info(
                "结构化输出成功 | model=%s | tokens=%s",
                model, response.usage.output_tokens,
            )
            return output_schema.model_validate_json(json_str)
        except Exception as e:
            wait = 2 ** attempt
            logger.warning("结构化输出失败 (attempt %d/%d): %s", attempt + 1, max_retries, e)
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


def count_tokens_estimate(text: str) -> int:
    """粗略估算 token 数（中文约1.5字符/token，英文约4字符/token）。"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)
