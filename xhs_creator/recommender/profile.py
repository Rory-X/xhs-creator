"""UserProfile - 构建和维护用户兴趣画像"""

import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from ..config import load_config
from ..tracker import load_traces

PROFILE_PATH = Path.home() / ".xhs-creator" / "profile.yaml"


def load_profile():
    # type: () -> Dict
    """加载用户画像，不存在则返回空画像结构"""
    if PROFILE_PATH.exists():
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if data else _empty_profile()
        except (yaml.YAMLError, OSError):
            return _empty_profile()
    return _empty_profile()


def _empty_profile():
    # type: () -> Dict
    return {
        "interests": {"primary": "", "domains": {}},
        "style_preference": {"preferred": [], "avoid": []},
        "created_topics": [],
        "feedback_history": {
            "liked_recommendations": [],
            "disliked_recommendations": [],
        },
        "updated_at": None,
    }


def save_profile(profile):
    # type: (Dict) -> None
    """保存画像到 YAML"""
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def build_profile(force_rebuild=False):
    # type: (bool) -> Dict
    """
    从 config + traces 构建/更新画像:
    1. config.domains -> interests.domains (source: "config")
    2. traces -> 统计高分领域/风格 -> interests.domains (source: "history")
    3. traces -> 提取已创作 topic -> created_topics
    4. 合并权重
    5. save_profile
    """
    if not force_rebuild:
        existing = load_profile()
        if existing.get("updated_at"):
            return existing

    profile = _empty_profile()
    cfg = load_config()

    # 1. 从 config.domains 构建基础兴趣
    domains_cfg = cfg.get("domains", {})
    primary = domains_cfg.get("primary", "")
    secondary = domains_cfg.get("secondary", [])

    if primary:
        profile["interests"]["primary"] = primary
        profile["interests"]["domains"][primary] = {"weight": 0.9, "source": "config"}

    for domain in secondary:
        profile["interests"]["domains"][domain] = {"weight": 0.5, "source": "config"}

    # 2. 从 traces 中提取统计数据
    traces = load_traces()
    if traces:
        # 统计高分风格
        style_ratings = defaultdict(list)
        for t in traces:
            fb = t.get("feedback", {})
            rating = fb.get("rating")
            if rating is None:
                continue
            options = t.get("input", {}).get("options", {})
            style = options.get("style", "")
            if style:
                style_ratings[style].append(rating)

        # 找到高分和低分风格
        preferred = []
        avoid = []
        for style, ratings in style_ratings.items():
            avg = sum(ratings) / len(ratings)
            if avg >= 4.0:
                preferred.append(style)
            elif avg <= 2.0 and len(ratings) >= 3:
                avoid.append(style)

        profile["style_preference"]["preferred"] = preferred
        profile["style_preference"]["avoid"] = avoid

        # 从 trace 中提取关键词作为兴趣域（基于 topic/write 命令的 query）
        # 只使用短查询（<=30字）作为领域关键词，避免长 prompt 文本污染画像
        keyword_ratings = defaultdict(list)
        for t in traces:
            fb = t.get("feedback", {})
            rating = fb.get("rating")
            query = t.get("input", {}).get("query", "")
            if rating and query and len(query) <= 30:
                keyword_ratings[query].append(rating)

        for kw, ratings in keyword_ratings.items():
            avg = sum(ratings) / len(ratings)
            if avg >= 3.5 and kw not in profile["interests"]["domains"]:
                profile["interests"]["domains"][kw] = {
                    "weight": min(0.7, round(avg / 5.0, 2)),
                    "source": "history",
                }

        # 3. 提取已创作话题
        created = []
        for t in traces:
            if t.get("command") in ("write", "topic"):
                query = t.get("input", {}).get("query", "")
                ts = t.get("timestamp", "")[:10]
                rating = t.get("feedback", {}).get("rating")
                if query:
                    # 截断过长的 query，只保留前 50 字作为话题摘要
                    topic_text = query[:50] + ("..." if len(query) > 50 else "")
                    created.append({
                        "topic": topic_text,
                        "date": ts,
                        "rating": rating,
                    })

        profile["created_topics"] = created

    save_profile(profile)
    return profile


def get_created_topics():
    # type: () -> List[str]
    """从画像中获取已创作话题列表"""
    profile = load_profile()
    return [item["topic"] for item in profile.get("created_topics", []) if item.get("topic")]


def update_from_feedback(rec_id, liked):
    # type: (str, bool) -> None
    """根据推荐反馈更新画像"""
    profile = load_profile()
    fh = profile.get("feedback_history", {
        "liked_recommendations": [],
        "disliked_recommendations": [],
    })

    if liked:
        if rec_id not in fh.get("liked_recommendations", []):
            fh.setdefault("liked_recommendations", []).append(rec_id)
    else:
        if rec_id not in fh.get("disliked_recommendations", []):
            fh.setdefault("disliked_recommendations", []).append(rec_id)

    profile["feedback_history"] = fh
    save_profile(profile)


def add_domain(domain):
    # type: (str) -> None
    """手动添加兴趣领域"""
    profile = load_profile()
    profile["interests"]["domains"][domain] = {"weight": 0.7, "source": "manual"}
    save_profile(profile)


def remove_domain(domain):
    # type: (str) -> None
    """手动移除兴趣领域"""
    profile = load_profile()
    profile["interests"]["domains"].pop(domain, None)
    if profile["interests"].get("primary") == domain:
        profile["interests"]["primary"] = ""
    save_profile(profile)
