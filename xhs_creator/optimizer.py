"""Optimizer 模块 - Prompt 版本化存储、查看、回滚"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

PROMPT_VERSIONS_DIR = Path.home() / ".xhs-creator" / "prompt_versions"

# 内置模板名列表
TEMPLATE_NAMES = [
    "TOPIC_SYSTEM_PROMPT",
    "TITLE_SYSTEM_PROMPT",
    "WRITE_SYSTEM_PROMPT",
    "ANALYZE_SYSTEM_PROMPT",
    "RECOMMEND_SYSTEM_PROMPT",
]


def _template_dir(template_name):
    # type: (str) -> Path
    """返回模板版本目录"""
    d = PROMPT_VERSIONS_DIR / template_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_current_version(template_name):
    # type: (str) -> Optional[str]
    """读取 current 文件获取当前版本号"""
    current_file = _template_dir(template_name) / "current"
    if current_file.exists():
        return current_file.read_text(encoding="utf-8").strip()
    return None


def get_current_prompt(template_name):
    # type: (str) -> Optional[str]
    """
    获取当前生效的 prompt 内容
    返回 None 时 fallback 到内置模板
    """
    version = _get_current_version(template_name)
    if not version:
        return None
    return get_prompt_by_version(template_name, version)


def get_prompt_by_version(template_name, version):
    # type: (str, str) -> Optional[str]
    """读取指定版本的 prompt 内容"""
    version_file = _template_dir(template_name) / "{}.json".format(version)
    if not version_file.exists():
        return None
    data = json.loads(version_file.read_text(encoding="utf-8"))
    return data.get("content")


def list_versions(template_name):
    # type: (str) -> List[Dict]
    """
    列出所有版本，按创建时间倒序
    每条: {version, created_at, change_summary, is_current}
    """
    tdir = _template_dir(template_name)
    current = _get_current_version(template_name)

    versions = []
    for f in tdir.glob("v*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            version = data.get("version", f.stem)
            versions.append({
                "version": version,
                "created_at": data.get("created_at", ""),
                "change_summary": data.get("change_summary", ""),
                "is_current": version == current,
            })
        except (json.JSONDecodeError, OSError):
            continue

    versions.sort(key=lambda v: v["created_at"], reverse=True)
    return versions


def save_version(
    template_name,      # type: str
    content,            # type: str
    change_summary,     # type: str
    change_reason,      # type: str
    metrics=None,       # type: Optional[Dict]
):
    # type: (...) -> str
    """
    保存新版本:
    1. 读取当前版本号 -> 计算下一版本号 (v1, v2, ...)
    2. 写入 {version}.json
    3. 更新 current 文件
    返回新版本号
    """
    tdir = _template_dir(template_name)
    current = _get_current_version(template_name)

    # 计算下一版本号
    if current:
        try:
            num = int(current.lstrip("v"))
            next_version = "v{}".format(num + 1)
        except ValueError:
            next_version = "v1"
    else:
        next_version = "v1"

    version_data = {
        "version": next_version,
        "template_name": template_name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "parent_version": current,
        "content": content,
        "change_summary": change_summary,
        "change_reason": change_reason,
        "metrics_at_creation": metrics,
    }

    version_file = tdir / "{}.json".format(next_version)
    version_file.write_text(
        json.dumps(version_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 更新 current
    current_file = tdir / "current"
    current_file.write_text(next_version, encoding="utf-8")

    return next_version


def rollback(template_name, target_version=None):
    # type: (str, Optional[str]) -> str
    """
    回滚:
    - target_version 指定时回滚到该版本
    - 未指定时回滚到 parent_version
    更新 current 文件，返回回滚到的版本号
    """
    tdir = _template_dir(template_name)
    current = _get_current_version(template_name)

    if target_version:
        # 验证目标版本存在
        version_file = tdir / "{}.json".format(target_version)
        if not version_file.exists():
            raise ValueError("版本 {} 不存在".format(target_version))
        new_version = target_version
    else:
        # 回滚到 parent
        if not current:
            raise ValueError("无版本可回滚")
        current_file = tdir / "{}.json".format(current)
        if not current_file.exists():
            raise ValueError("当前版本文件不存在")
        data = json.loads(current_file.read_text(encoding="utf-8"))
        parent = data.get("parent_version")
        if not parent:
            raise ValueError("已是最早版本，无法回滚")
        new_version = parent

    # 更新 current
    current_file = tdir / "current"
    current_file.write_text(new_version, encoding="utf-8")

    return new_version


def reset_to_default(template_name):
    # type: (str) -> None
    """删除 current 文件 -> get_current_prompt 返回 None -> fallback 到内置"""
    current_file = _template_dir(template_name) / "current"
    if current_file.exists():
        current_file.unlink()


# --- Phase 5 占位 ---

def suggest_optimization(template_name, report):
    # type: (str, Dict) -> List[Dict]
    """
    基于分析报告，调用 LLM 生成优化建议（Phase 5 实现）
    每条: {modification, reason, expected_effect}
    """
    return []


def apply_optimization(template_name, suggestion):
    # type: (str, Dict) -> str
    """应用优化建议，保存为新版本（Phase 5 实现）"""
    return ""
