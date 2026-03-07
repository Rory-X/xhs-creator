"""Recommender 主引擎 - 组合趋势、画像、评分生成推荐"""

import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..config import load_config
from ..llm import call_llm, parse_llm_json
from .calendar import get_boost_tags, get_current_events
from .profile import get_created_topics, load_profile
from .scorer import compute_freshness, rank_topics, score_topic
from .trends import collect_trends

RECOMMENDATIONS_DIR = Path.home() / ".xhs-creator" / "recommendations"

RECOMMEND_SYSTEM_PROMPT = """你是小红书选题推荐专家。

用户画像：
- 擅长领域: {domains}
- 偏好风格: {preferred_styles}
- 已创作过的话题: {created_topics}

当前平台趋势:
{trends_summary}

时间因素:
- 当前日期: {current_date}
- 相关节日/季节: {calendar_events}

请推荐 {count} 个适合该用户创作的小红书选题。

返回 JSON:
{{
  "recommendations": [
    {{
      "topic": "推荐话题标题",
      "reason": "推荐理由",
      "heat_score": 1到5的整数,
      "suggested_style": "建议风格",
      "suggested_tone": "建议语气",
      "tags": ["标签1", "标签2"]
    }}
  ]
}}

重要：只返回纯JSON，不要markdown代码块，不要解释文字，不要<think>标签。"""


class Recommender:
    def generate_recommendations(
        self,
        n=5,            # type: int
        domain=None,    # type: Optional[str]
        explore=False,  # type: bool
        refresh=False,  # type: bool
    ):
        # type: (...) -> List[Dict]
        """
        推荐主流程:
        1. load_profile()
        2. collect_trends(domains, force_refresh=refresh)
        3. get_current_events()
        4. 构造 prompt -> call_llm -> 生成 n*2 个候选
        5. score_topic 评分
        6. 去重（vs created_topics）
        7. explore -> _inject_exploration()
        8. 取 top n，缓存结果
        """
        cfg = load_config()
        weights = cfg.get("recommend", {}).get("weights")

        # 1. 加载用户画像
        profile = load_profile()

        # 2. 采集趋势（带缓存）
        if domain:
            domains = [domain]
        else:
            domains = self._get_domains(profile, cfg)

        trends = {}
        if domains:
            try:
                trends = collect_trends(domains, force_refresh=refresh)
            except Exception:
                pass  # MCP 不可用时降级

        # 3. 获取时间因素
        calendar_events = get_current_events()
        boost_tags = get_boost_tags()

        # 4. 构造 LLM prompt
        context = self._build_context(profile, trends, calendar_events, boost_tags)
        candidates = self._llm_generate_topics(context, n=n * 2)

        if not candidates:
            return []

        # 5. 评分排序
        scored = []
        for t in candidates:
            scored_topic = score_topic(t, profile, trends, calendar_events, weights)
            scored.append(scored_topic)

        scored = rank_topics(scored, weights)

        # 6. 去重过滤
        created = get_created_topics()
        filtered = [t for t in scored if self._is_novel(t, created)]

        # 7. 探索模式
        if explore:
            filtered = self._inject_exploration(filtered, trends, profile, cfg)

        # 取 top n
        result = filtered[:n]

        # 添加 ID
        for i, rec in enumerate(result, 1):
            rec["id"] = "rec_{:03d}".format(i)

        # 缓存
        self._save_cache(result, profile)

        return result

    def get_cached_recommendations(self):
        # type: () -> Optional[List[Dict]]
        """读取当日缓存的推荐结果"""
        cache_path = self._cache_path()
        if not cache_path.exists():
            return None
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return data.get("recommendations")
        except (json.JSONDecodeError, OSError):
            return None

    def pick_recommendation(self, index):
        # type: (int) -> Optional[Dict]
        """选择第 index 个推荐（1-based）"""
        cached = self.get_cached_recommendations()
        if not cached:
            return None
        if 1 <= index <= len(cached):
            return cached[index - 1]
        return None

    def feedback(self, rec_id, liked):
        # type: (str, bool) -> None
        """对推荐点赞/踩"""
        from .profile import update_from_feedback
        update_from_feedback(rec_id, liked)

    def _get_domains(self, profile, cfg):
        # type: (Dict, Dict) -> List[str]
        """获取用户的领域列表"""
        domains = []

        # 从画像获取
        domain_dict = profile.get("interests", {}).get("domains", {})
        for d in domain_dict:
            if d not in domains:
                domains.append(d)

        # 从配置获取
        domains_cfg = cfg.get("domains", {})
        primary = domains_cfg.get("primary", "")
        if primary and primary not in domains:
            domains.insert(0, primary)
        for d in domains_cfg.get("secondary", []):
            if d not in domains:
                domains.append(d)

        # 额外采集领域
        extra = cfg.get("recommend", {}).get("auto_collect_domains", [])
        for d in extra:
            if d not in domains:
                domains.append(d)

        return domains

    def _build_context(self, profile, trends, calendar_events, boost_tags):
        # type: (Dict, Dict, List[Dict], List[str]) -> Dict
        """构造 LLM 上下文"""
        domains = list(profile.get("interests", {}).get("domains", {}).keys())
        preferred = profile.get("style_preference", {}).get("preferred", [])
        created = [item.get("topic", "") for item in profile.get("created_topics", [])[:10]]

        # 趋势摘要
        trends_lines = []
        for domain, data in trends.items():
            hot_topics = data.get("hot_topics", [])[:3]
            for t in hot_topics:
                trends_lines.append(
                    "- {}: {} (趋势: {}, 均赞: {})".format(
                        domain, t.get("keyword", ""),
                        t.get("trend", ""), t.get("avg_likes", "-")
                    )
                )
            hot_tags = data.get("hot_tags", [])[:5]
            if hot_tags:
                trends_lines.append("  热门标签: {}".format(", ".join(hot_tags)))

        calendar_names = [e.get("name", "") for e in calendar_events]

        return {
            "domains": ", ".join(domains) if domains else "通用",
            "preferred_styles": ", ".join(preferred) if preferred else "多样化",
            "created_topics": ", ".join(created) if created else "无",
            "trends_summary": "\n".join(trends_lines) if trends_lines else "暂无趋势数据",
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "calendar_events": ", ".join(calendar_names) if calendar_names else "无",
        }

    def _llm_generate_topics(self, context, n=10):
        # type: (Dict, int) -> List[Dict]
        """调用 LLM 生成候选话题"""
        prompt = RECOMMEND_SYSTEM_PROMPT.format(count=n, **context)

        result = call_llm(
            "推荐选题",
            prompt,
            track=False,
        )

        if "error" in result:
            return []

        parsed = parse_llm_json(result.get("content", ""))
        if not parsed:
            return []

        return parsed.get("recommendations", [])

    def _is_novel(self, topic, created_topics):
        # type: (Dict, List[str]) -> bool
        """检查话题是否与已创作内容重复"""
        freshness = compute_freshness(topic, created_topics)
        return freshness > 0.3  # 相似度超过 70% 认为重复

    def _inject_exploration(self, topics, trends, profile, cfg):
        # type: (List[Dict], Dict, Dict, Dict) -> List[Dict]
        """在推荐中插入 1-2 个跨领域话题"""
        explore_ratio = cfg.get("recommend", {}).get("explore_ratio", 0.2)
        n_explore = max(1, int(len(topics) * explore_ratio))

        # 从趋势中找到用户领域外的热门话题
        user_domains = set(profile.get("interests", {}).get("domains", {}).keys())
        cross_domain_topics = []

        for domain, data in trends.items():
            if domain not in user_domains:
                for ht in data.get("hot_topics", [])[:2]:
                    cross_domain_topics.append({
                        "topic": ht.get("keyword", ""),
                        "reason": "跨领域探索: {} 领域热门话题".format(domain),
                        "heat_score": 4,
                        "suggested_style": "教程",
                        "suggested_tone": "专业",
                        "tags": data.get("hot_tags", [])[:3],
                        "final_score": 0.5,
                        "is_exploration": True,
                    })

        if cross_domain_topics:
            random.shuffle(cross_domain_topics)
            # 在结果中插入探索话题
            insert_at = len(topics) // 2 if topics else 0
            for t in cross_domain_topics[:n_explore]:
                topics.insert(insert_at, t)

        return topics

    def _cache_path(self):
        # type: () -> Path
        """当日推荐缓存路径"""
        RECOMMENDATIONS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        return RECOMMENDATIONS_DIR / "recommendations-{}.json".format(date_str)

    def _save_cache(self, recommendations, profile):
        # type: (List[Dict], Dict) -> None
        """缓存推荐结果"""
        cache_data = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "profile_version": datetime.now().strftime("%Y-%m-%d"),
            "recommendations": recommendations,
        }
        cache_path = self._cache_path()
        cache_path.write_text(
            json.dumps(cache_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
