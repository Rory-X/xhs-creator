"""TopicScorer - 多维度话题评分与排序"""

from typing import Dict, List, Optional


def score_topic(
    topic,              # type: Dict
    profile,            # type: Dict
    trends,             # type: Dict
    calendar_events,    # type: List[Dict]
    weights=None,       # type: Optional[Dict]
):
    # type: (...) -> Dict
    """
    综合评分，返回 topic dict 增加 *_score 和 final_score 字段

    默认权重: trend=0.3, match=0.3, freshness=0.25, timeliness=0.15
    """
    if weights is None:
        weights = {"trend": 0.3, "match": 0.3, "freshness": 0.25, "timeliness": 0.15}

    created_topics = [
        item["topic"] for item in profile.get("created_topics", [])
        if item.get("topic")
    ]

    trend_score = compute_trend_score(topic, trends)
    match_score = compute_match_score(topic, profile)
    freshness_score = compute_freshness(topic, created_topics)
    timeliness_score = compute_timeliness(topic, calendar_events)

    final = (
        weights.get("trend", 0.3) * trend_score
        + weights.get("match", 0.3) * match_score
        + weights.get("freshness", 0.25) * freshness_score
        + weights.get("timeliness", 0.15) * timeliness_score
    )

    scored = dict(topic)
    scored["trend_score"] = round(trend_score, 3)
    scored["match_score"] = round(match_score, 3)
    scored["freshness_score"] = round(freshness_score, 3)
    scored["timeliness_score"] = round(timeliness_score, 3)
    scored["final_score"] = round(final, 3)

    return scored


def compute_trend_score(topic, trends):
    # type: (Dict, Dict) -> float
    """
    话题在趋势中的热度 (0-1)
    用关键词匹配: topic.topic vs trends.hot_keywords/hot_tags
    """
    topic_text = topic.get("topic", "")
    topic_tags = set(topic.get("tags", []))
    topic_words = set(_extract_words(topic_text))

    if not trends:
        return 0.5  # 无趋势数据时给中等分

    all_hot_keywords = set()
    all_hot_tags = set()

    for domain, data in trends.items():
        all_hot_keywords.update(data.get("hot_keywords", []))
        all_hot_tags.update(data.get("hot_tags", []))

    if not all_hot_keywords and not all_hot_tags:
        return 0.5

    # 计算匹配
    keyword_matches = len(topic_words & all_hot_keywords)
    tag_matches = len(topic_tags & all_hot_tags)

    total_possible = max(len(topic_words) + len(topic_tags), 1)
    score = min(1.0, (keyword_matches + tag_matches) / total_possible * 2)

    # 如果 topic 本身在热门关键词中，额外加分
    for kw in all_hot_keywords:
        if kw in topic_text:
            score = min(1.0, score + 0.2)
            break

    return score


def compute_match_score(topic, profile):
    # type: (Dict, Dict) -> float
    """
    话题与用户兴趣的匹配度 (0-1)
    用关键词重叠: topic.tags vs profile.interests.domains
    """
    topic_text = topic.get("topic", "")
    topic_tags = set(topic.get("tags", []))
    topic_words = set(_extract_words(topic_text))

    domains = profile.get("interests", {}).get("domains", {})
    if not domains:
        return 0.5

    domain_names = set(domains.keys())
    preferred_styles = set(profile.get("style_preference", {}).get("preferred", []))
    avoid_styles = set(profile.get("style_preference", {}).get("avoid", []))

    # 领域匹配
    domain_match = 0
    for d in domain_names:
        weight = domains[d].get("weight", 0.5)
        if d in topic_text or d in topic_tags:
            domain_match += weight
        else:
            # 检查 topic 关键词与领域的部分匹配
            for w in topic_words:
                if w in d or d in w:
                    domain_match += weight * 0.5
                    break

    score = min(1.0, domain_match)

    # 风格匹配加分/减分
    suggested_style = topic.get("suggested_style", "")
    if suggested_style in preferred_styles:
        score = min(1.0, score + 0.15)
    if suggested_style in avoid_styles:
        score = max(0.0, score - 0.2)

    return score


def compute_freshness(topic, created_topics):
    # type: (Dict, List[str]) -> float
    """
    新鲜度 (0-1): 与已创作话题的相似度取反
    """
    if not created_topics:
        return 1.0

    topic_text = topic.get("topic", "")
    topic_bigrams = set(_bigrams(topic_text))

    max_similarity = 0.0
    for existing in created_topics:
        existing_bigrams = set(_bigrams(existing))
        similarity = _jaccard(topic_bigrams, existing_bigrams)
        if similarity > max_similarity:
            max_similarity = similarity

    return round(1.0 - max_similarity, 3)


def compute_timeliness(topic, calendar_events):
    # type: (Dict, List[Dict]) -> float
    """
    时效性 (0-1): 话题与当前时间因素的关联
    """
    if not calendar_events:
        return 0.0

    topic_text = topic.get("topic", "")
    topic_tags = set(topic.get("tags", []))
    topic_words = set(_extract_words(topic_text))

    all_boost_tags = set()
    for event in calendar_events:
        all_boost_tags.update(event.get("boost_tags", []))

    if not all_boost_tags:
        return 0.0

    # 匹配 boost_tags
    matches = 0
    for tag in all_boost_tags:
        if tag in topic_text or tag in topic_tags or tag in topic_words:
            matches += 1

    return min(1.0, matches / max(len(all_boost_tags), 1) * 3)


def rank_topics(topics, weights=None):
    # type: (List[Dict], Optional[Dict]) -> List[Dict]
    """按 final_score 降序排序"""
    topics.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    return topics


def _extract_words(text):
    # type: (str) -> List[str]
    """简单的中文分词：按标点和空格分割，取 2-4 字的片段"""
    import re
    # 去除标点
    text = re.sub(r'[^\w\u4e00-\u9fff]', ' ', text)
    parts = text.split()
    words = []
    for p in parts:
        words.append(p)
        # 对较长的中文文本，提取 bigram
        if len(p) > 2:
            for i in range(len(p) - 1):
                words.append(p[i:i+2])
    return words


def _bigrams(text):
    # type: (str) -> List[str]
    """提取字符 bigram 用于相似度计算"""
    import re
    text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
    if len(text) < 2:
        return [text] if text else []
    return [text[i:i+2] for i in range(len(text) - 1)]


def _jaccard(set_a, set_b):
    # type: (set, set) -> float
    """Jaccard 相似度"""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0
