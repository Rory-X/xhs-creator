"""Analyzer 模块 - 分析历史调用数据，识别高效 prompt 模式"""

from collections import defaultdict
from typing import Dict, List, Optional


def compute_stats(traces):
    # type: (List[Dict]) -> Dict
    """
    计算基础统计:
    - total_traces, rated_traces, avg_rating, adopt_rate, publish_rate
    - by_command: {command: {count, avg_rating, adopt_rate}}
    """
    total = len(traces)
    if total == 0:
        return {
            "total_traces": 0,
            "rated_traces": 0,
            "avg_rating": 0,
            "adopt_rate": 0,
            "publish_rate": 0,
            "by_command": {},
        }

    rated_traces = []
    adopted_count = 0
    published_count = 0
    rating_sum = 0

    by_command = defaultdict(lambda: {
        "count": 0, "ratings": [], "adopted": 0, "total_with_feedback": 0
    })

    for t in traces:
        fb = t.get("feedback", {})
        cmd = t.get("command", "unknown")

        by_command[cmd]["count"] += 1

        rating = fb.get("rating")
        if rating is not None:
            rated_traces.append(t)
            rating_sum += rating
            by_command[cmd]["ratings"].append(rating)

        adopted = fb.get("adopted")
        if adopted is True:
            adopted_count += 1
            by_command[cmd]["adopted"] += 1
        if adopted is not None:
            by_command[cmd]["total_with_feedback"] += 1

        if fb.get("published"):
            published_count += 1

    rated_count = len(rated_traces)
    avg_rating = round(rating_sum / rated_count, 2) if rated_count > 0 else 0

    # 采用率基于有反馈的 trace
    total_with_adopt = sum(1 for t in traces if t.get("feedback", {}).get("adopted") is not None)
    adopt_rate = round(adopted_count / total_with_adopt, 2) if total_with_adopt > 0 else 0
    publish_rate = round(published_count / total, 2) if total > 0 else 0

    # 构建 by_command
    by_command_result = {}
    for cmd, data in by_command.items():
        cmd_avg = round(sum(data["ratings"]) / len(data["ratings"]), 2) if data["ratings"] else 0
        cmd_adopt = round(data["adopted"] / data["total_with_feedback"], 2) if data["total_with_feedback"] > 0 else 0
        by_command_result[cmd] = {
            "count": data["count"],
            "avg_rating": cmd_avg,
            "adopt_rate": cmd_adopt,
        }

    return {
        "total_traces": total,
        "rated_traces": rated_count,
        "avg_rating": avg_rating,
        "adopt_rate": adopt_rate,
        "publish_rate": publish_rate,
        "by_command": by_command_result,
    }


def find_top_combinations(
    traces,         # type: List[Dict]
    top_k=5,        # type: int
    min_count=3,    # type: int
):
    # type: (...) -> List[Dict]
    """
    交叉分析 style x tone x length -> avg_rating
    只返回 count >= min_count 的组合，按 avg_rating 降序取 top_k
    """
    return _find_combinations(traces, top_k, min_count, best=True)


def find_worst_combinations(
    traces,         # type: List[Dict]
    bottom_k=3,     # type: int
    min_count=3,    # type: int
):
    # type: (...) -> List[Dict]
    """与 find_top_combinations 相反，取最低评分"""
    return _find_combinations(traces, bottom_k, min_count, best=False)


def _find_combinations(traces, k, min_count, best=True):
    # type: (List[Dict], int, int, bool) -> List[Dict]
    """内部通用函数，按评分排序参数组合"""
    groups = defaultdict(list)

    for t in traces:
        fb = t.get("feedback", {})
        rating = fb.get("rating")
        if rating is None:
            continue

        options = t.get("input", {}).get("options", {})
        style = options.get("style", "")
        tone = options.get("tone", "")
        length = options.get("length", "")

        key = (style, tone, length)
        groups[key].append(rating)

    results = []
    for (style, tone, length), ratings in groups.items():
        if len(ratings) < min_count:
            continue
        avg = round(sum(ratings) / len(ratings), 2)
        results.append({
            "style": style,
            "tone": tone,
            "length": length,
            "avg_rating": avg,
            "count": len(ratings),
        })

    results.sort(key=lambda x: x["avg_rating"], reverse=best)
    return results[:k]


def compare_prompt_versions(
    traces,         # type: List[Dict]
    template_name,  # type: str
):
    # type: (...) -> Dict
    """
    按 prompt.template_version 分组，对比不同版本的 avg_rating
    返回: {version: {count, avg_rating, adopt_rate}}
    """
    groups = defaultdict(lambda: {"ratings": [], "adopted": 0, "total_with_feedback": 0})

    for t in traces:
        prompt = t.get("prompt", {})
        if prompt.get("template_name") != template_name:
            continue

        version = prompt.get("template_version", "unknown")
        fb = t.get("feedback", {})

        rating = fb.get("rating")
        if rating is not None:
            groups[version]["ratings"].append(rating)

        adopted = fb.get("adopted")
        if adopted is True:
            groups[version]["adopted"] += 1
        if adopted is not None:
            groups[version]["total_with_feedback"] += 1

    result = {}
    for version, data in groups.items():
        avg = round(sum(data["ratings"]) / len(data["ratings"]), 2) if data["ratings"] else 0
        adopt_rate = round(data["adopted"] / data["total_with_feedback"], 2) if data["total_with_feedback"] > 0 else 0
        result[version] = {
            "count": len(data["ratings"]),
            "avg_rating": avg,
            "adopt_rate": adopt_rate,
        }

    return result


def generate_report(
    since=None,     # type: Optional[str]
    until=None,     # type: Optional[str]
    command=None,   # type: Optional[str]
):
    # type: (...) -> Dict
    """
    生成完整分析报告:
    1. load_traces(since, until, command)
    2. compute_stats
    3. find_top/worst_combinations
    4. 组装 AnalysisReport dict
    """
    import time
    from .tracker import load_traces

    traces = load_traces(since=since, until=until, command=command)
    stats = compute_stats(traces)
    top = find_top_combinations(traces)
    worst = find_worst_combinations(traces)

    # 生成优化建议
    suggestions = _generate_suggestions(stats, top, worst)

    report = {
        "report_id": "rpt_" + time.strftime("%Y%m%d"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "period": {
            "from": since or "all",
            "to": until or "now",
        },
        "summary": stats,
        "top_combinations": top,
        "worst_combinations": worst,
        "optimization_suggestions": suggestions,
    }

    return report


def _generate_suggestions(stats, top, worst):
    # type: (Dict, List[Dict], List[Dict]) -> List[str]
    """基于统计数据生成文本优化建议"""
    suggestions = []

    # 基于 top combinations
    if top:
        best = top[0]
        parts = []
        if best.get("style"):
            parts.append(f"风格「{best['style']}」")
        if best.get("tone"):
            parts.append(f"语气「{best['tone']}」")
        if best.get("length"):
            parts.append(f"篇幅「{best['length']}」")
        if parts:
            suggestions.append(
                f"最佳参数组合: {'、'.join(parts)}，平均评分 {best['avg_rating']}（{best['count']} 次）"
            )

    # 基于 worst combinations
    if worst:
        w = worst[0]
        parts = []
        if w.get("style"):
            parts.append(f"风格「{w['style']}」")
        if w.get("tone"):
            parts.append(f"语气「{w['tone']}」")
        if w.get("length"):
            parts.append(f"篇幅「{w['length']}」")
        if parts:
            suggestions.append(
                f"建议避免组合: {'、'.join(parts)}，平均评分仅 {w['avg_rating']}（{w['count']} 次）"
            )

    # 基于 by_command 分析
    by_cmd = stats.get("by_command", {})
    if by_cmd:
        best_cmd = max(by_cmd.items(), key=lambda x: x[1].get("avg_rating", 0))
        if best_cmd[1].get("avg_rating", 0) > 0:
            suggestions.append(
                f"命令 {best_cmd[0]} 表现最好，平均评分 {best_cmd[1]['avg_rating']}"
            )

    if not suggestions:
        suggestions.append("数据量不足，继续使用并评分以获得更准确的分析")

    return suggestions
