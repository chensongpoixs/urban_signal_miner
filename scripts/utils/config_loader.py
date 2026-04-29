"""配置加载工具。读取 config/ 目录下的所有 YAML 文件。"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


def _load_yaml(filename: str) -> dict:
    """加载单个 YAML 配置文件。"""
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_settings() -> dict:
    """获取全局配置。"""
    return _load_yaml("settings.yaml")


def get_cities() -> List[Dict[str, Any]]:
    """获取城市配置列表。"""
    data = _load_yaml("cities.yaml")
    return data.get("cities", [])


def get_city_keywords() -> Dict[str, List[str]]:
    """获取 {城市名: [关键词列表]} 映射。"""
    cities = get_cities()
    return {c["name"]: c.get("keywords", []) for c in cities}


def get_domains() -> List[Dict[str, Any]]:
    """获取领域配置列表。"""
    data = _load_yaml("domains.yaml")
    return data.get("domains", [])


def get_source_weights() -> Dict[str, Dict[str, Any]]:
    """获取 {来源key: {name, weight, ...}} 映射。"""
    data = _load_yaml("source_weight.yaml")
    return data.get("sources", {})


def get_source_full_process_keys() -> List[str]:
    """获取需要全量处理的来源 key 列表。"""
    sources = get_source_weights()
    return [k for k, v in sources.items() if v.get("full_process", False)]
