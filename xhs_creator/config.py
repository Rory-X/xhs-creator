"""配置管理模块 - 加载/保存/默认值合并"""

import copy
from pathlib import Path

import yaml


CONFIG_DIR = Path.home() / ".xhs-creator"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
HISTORY_DIR = CONFIG_DIR / "history"

DEFAULT_CONFIG = {
    "llm": {
        "api_url": "https://chat.tabcode.cc/v1/chat/completions",
        "api_key": "",
        "model": "grok-4.20-beta",
        "temperature": 0.7,
        "timeout": 300,
    },
    "xhs": {
        "mcp_port": 18060,
        "auto_start": True,
        "tools_path": "/home/node/clawd/tools/xhs.py",
    },
    "defaults": {
        "style": "种草",
        "tone": "活泼",
        "length": "medium",
        "emoji": True,
        "max_title_length": 20,
    },
    "domains": {
        "primary": "",
        "secondary": [],
        "custom_tags": [],
        "auto_topic": False,
    },
    "image_gen": {
        "enabled": False,
        "api_url": "https://chat.tabcode.cc/v1/chat/completions",
        "api_key": "sk-mJdvWysFfFSoRJLH5YHPVWvUUrReQg6bZC3ckE2YLyRim0dV",
        "model": "gemini-3.1-flash-image-three-four",
        "style": "小红书风格，色彩鲜明，扁平插画",
    },
    "output": {
        "format": "text",
        "color": True,
        "save_history": True,
        "history_dir": str(HISTORY_DIR),
    },
}


def ensure_config_dir():
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _deep_merge(base, override):
    """深度合并两个字典，override 覆盖 base"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config():
    """加载配置文件，与默认值深度合并"""
    ensure_config_dir()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        return _deep_merge(DEFAULT_CONFIG, user_config)
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config(cfg):
    """保存配置到文件"""
    ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_value(key):
    """通过点号路径获取配置值，如 'llm.model'"""
    cfg = load_config()
    keys = key.split(".")
    current = cfg
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return None
    return current


def set_value(key, value):
    """通过点号路径设置配置值，自动进行类型转换"""
    cfg = load_config()
    keys = key.split(".")
    current = cfg
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]

    # 根据原值类型自动转换
    old_value = current.get(keys[-1])
    if old_value is not None:
        if isinstance(old_value, bool):
            value = str(value).lower() in ("true", "1", "yes")
        elif isinstance(old_value, int):
            value = int(value)
        elif isinstance(old_value, float):
            value = float(value)

    current[keys[-1]] = value
    save_config(cfg)
    return value


def reset_config():
    """恢复默认配置"""
    save_config(copy.deepcopy(DEFAULT_CONFIG))
