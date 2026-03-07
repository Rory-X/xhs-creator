"""TrendCollector - 从小红书采集热门话题数据并缓存"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..config import load_config
from ..llm import call_llm, parse_llm_json
from ..xhs_client import ensure_mcp_running, search_notes

TRENDS_DIR = Path.home() / ".xhs-creator" / "trends"

TREND_EXTRACT_PROMPT = """分析以下小红书笔记搜索结果，提取趋势数据。

搜索结果：
{search_content}

返回 JSON：
{{
  "hot_topics": [
    {{
      "keyword": "热门关键词",
      "mention_count": 出现次数估算,
      "avg_likes": 平均点赞数估算,
      "avg_collects": 平均收藏数估算,
      "trend": "rising/stable/declining",
      "sample_titles": ["示例标题1", "示例标题2"]
    }}
  ],
  "hot_tags": ["高频标签1", "高频标签2"],
  "hot_keywords": ["高频词1", "高频词2"]
}}

重要：只返回纯JSON，不要markdown代码块，不要解释文字，不要<think>标签。"""


def _cache_path(domain):
    # type: (str) -> Path
    """趋势缓存文件路径"""
    TRENDS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    return TRENDS_DIR / "trends-{}-{}.json".format(domain, date_str)


def is_cache_valid(domain):
    # type: (str) -> bool
    """检查缓存是否在 TTL 内"""
    path = _cache_path(domain)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        collected_at = data.get("collected_at", "")
        ttl_hours = data.get("ttl_hours", 6)

        if not collected_at:
            return False

        # 解析 collected_at 时间
        collected_time = datetime.strptime(collected_at[:19], "%Y-%m-%dT%H:%M:%S")
        elapsed_hours = (datetime.now() - collected_time).total_seconds() / 3600
        return elapsed_hours < ttl_hours
    except (json.JSONDecodeError, ValueError, OSError):
        return False


def get_cached_trends(domain):
    # type: (str) -> Optional[Dict]
    """读取缓存的趋势数据"""
    path = _cache_path(domain)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def collect_trends(domains, force_refresh=False):
    # type: (List[str], bool) -> Dict[str, Dict]
    """
    采集多个领域的趋势数据

    1. 遍历 domains
    2. is_cache_valid -> 用缓存
    3. 否则: search_notes(domain) -> LLM 提取结构化趋势 -> 缓存
    4. MCP 不可用时返回空（降级）

    Returns: {domain: TrendData}
    """
    cfg = load_config()
    ttl_hours = cfg.get("recommend", {}).get("cache_ttl_hours", 6)
    result = {}

    for domain in domains:
        # 检查缓存
        if not force_refresh and is_cache_valid(domain):
            cached = get_cached_trends(domain)
            if cached:
                result[domain] = cached
                continue

        # 需要采集
        trend_data = _collect_single_domain(domain, ttl_hours)
        if trend_data:
            result[domain] = trend_data

    return result


def _collect_single_domain(domain, ttl_hours):
    # type: (str, int) -> Optional[Dict]
    """采集单个领域的趋势数据"""
    # 确保 MCP 服务运行
    mcp_status = ensure_mcp_running()
    if "error" in mcp_status:
        return None

    # 搜索笔记
    search_result = search_notes(domain, limit=15)
    if "error" in search_result:
        return None

    search_content = search_result.get("content", "")
    if not search_content:
        return None

    # 用 LLM 提取结构化趋势
    prompt = TREND_EXTRACT_PROMPT.format(search_content=search_content[:3000])
    llm_result = call_llm(
        "提取{}领域趋势".format(domain),
        prompt,
        track=False,
    )

    if "error" in llm_result:
        return None

    parsed = parse_llm_json(llm_result.get("content", ""))
    if not parsed:
        return None

    # 组装缓存数据
    trend_data = {
        "domain": domain,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ttl_hours": ttl_hours,
        "hot_topics": parsed.get("hot_topics", []),
        "hot_tags": parsed.get("hot_tags", []),
        "hot_keywords": parsed.get("hot_keywords", []),
    }

    # 写缓存
    cache_path = _cache_path(domain)
    cache_path.write_text(
        json.dumps(trend_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return trend_data


def refresh_trends(domain):
    # type: (str) -> Optional[Dict]
    """强制刷新单个领域的趋势"""
    return collect_trends([domain], force_refresh=True).get(domain)
