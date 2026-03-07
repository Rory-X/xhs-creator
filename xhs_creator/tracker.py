"""Tracker 模块 - 记录每次 LLM 调用的输入、参数、输出和用户反馈"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

TRACES_DIR = Path.home() / ".xhs-creator" / "traces"


def generate_trace_id() -> str:
    """生成唯一 trace_id: tr_YYYYMMDD_HHMMSS_6hex"""
    ts = time.strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"tr_{ts}_{suffix}"


def _get_trace_file() -> Path:
    """当月 JSONL 文件路径: traces-YYYY-MM.jsonl"""
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    month = time.strftime("%Y-%m")
    return TRACES_DIR / f"traces-{month}.jsonl"


def _get_last_trace_file() -> Path:
    """存储最近一次 trace_id 的文件"""
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    return TRACES_DIR / ".last_trace_id"


def start_trace(
    command,        # type: str
    query,          # type: str
    options,        # type: Dict[str, Any]
    prompt_info,    # type: Dict[str, str]
):
    # type: (...) -> str
    """
    记录调用开始，写入 JSONL

    Args:
        command: "topic" | "title" | "write" | "analyze" | "recommend"
        query: 用户输入
        options: {"style": ..., "tone": ..., "length": ...}
        prompt_info: {"template_name": ..., "template_version": ..., "rendered": ...}

    Returns:
        trace_id
    """
    trace_id = generate_trace_id()
    trace = {
        "trace_id": trace_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "command": command,
        "input": {
            "query": query,
            "options": options,
        },
        "prompt": prompt_info,
        "response": {
            "content": None,
            "parsed": None,
            "model": None,
            "tokens": None,
            "latency_ms": None,
        },
        "feedback": {
            "rating": None,
            "adopted": None,
            "published": False,
            "edit_distance": None,
            "feedback_time": None,
        },
    }

    trace_file = _get_trace_file()
    with open(trace_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    # 记录最近 trace_id
    last_file = _get_last_trace_file()
    last_file.write_text(trace_id, encoding="utf-8")

    return trace_id


def end_trace(
    trace_id,       # type: str
    content,        # type: str
    parsed,         # type: Optional[Any]
    model,          # type: str
    tokens,         # type: Optional[Dict[str, int]]
    latency_ms,     # type: int
):
    # type: (...) -> None
    """更新已有 trace 的 response 字段"""
    _update_trace(trace_id, {
        "response": {
            "content": content,
            "parsed": parsed,
            "model": model,
            "tokens": tokens,
            "latency_ms": latency_ms,
        }
    })


def add_feedback(
    trace_id,           # type: str
    rating=None,        # type: Optional[int]
    adopted=None,       # type: Optional[bool]
    published=None,     # type: Optional[bool]
    edit_distance=None,  # type: Optional[int]
):
    # type: (...) -> bool
    """更新 trace 的 feedback 字段，返回是否成功"""
    trace_file = _get_trace_file()
    if not trace_file.exists():
        # 搜索所有 trace 文件
        found = _find_trace_file(trace_id)
        if not found:
            return False
        trace_file = found

    lines = trace_file.read_text(encoding="utf-8").strip().split("\n")
    updated = False
    new_lines = []

    for line in lines:
        if not line.strip():
            continue
        trace = json.loads(line)
        if trace["trace_id"] == trace_id:
            feedback = trace.get("feedback", {})
            if rating is not None:
                feedback["rating"] = rating
            if adopted is not None:
                feedback["adopted"] = adopted
            if published is not None:
                feedback["published"] = published
            if edit_distance is not None:
                feedback["edit_distance"] = edit_distance
            feedback["feedback_time"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            trace["feedback"] = feedback
            updated = True
        new_lines.append(json.dumps(trace, ensure_ascii=False))

    if updated:
        trace_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return updated


def get_last_trace_id():
    # type: () -> Optional[str]
    """读取最近一次 trace_id"""
    last_file = _get_last_trace_file()
    if last_file.exists():
        return last_file.read_text(encoding="utf-8").strip()
    return None


def get_recent_traces(
    n=10,               # type: int
    command=None,       # type: Optional[str]
    rated_only=False,   # type: bool
):
    # type: (...) -> List[Dict]
    """获取最近 N 条 trace"""
    all_traces = _load_all_traces()

    if command:
        all_traces = [t for t in all_traces if t.get("command") == command]

    if rated_only:
        all_traces = [
            t for t in all_traces
            if t.get("feedback", {}).get("rating") is not None
        ]

    # 按时间倒序
    all_traces.sort(key=lambda t: t.get("timestamp", ""), reverse=True)

    return all_traces[:n]


def load_traces(
    since=None,     # type: Optional[str]
    until=None,     # type: Optional[str]
    command=None,   # type: Optional[str]
):
    # type: (...) -> List[Dict]
    """加载指定范围的所有 trace"""
    all_traces = _load_all_traces()

    result = []
    for t in all_traces:
        ts = t.get("timestamp", "")
        # 提取日期部分用于比较
        date_part = ts[:10] if len(ts) >= 10 else ts

        if since and date_part < since:
            continue
        if until and date_part > until:
            continue
        if command and t.get("command") != command:
            continue

        result.append(t)

    return result


def _update_trace(trace_id, updates):
    # type: (str, Dict) -> bool
    """更新 trace 中的指定字段"""
    trace_file = _get_trace_file()
    if not trace_file.exists():
        found = _find_trace_file(trace_id)
        if not found:
            return False
        trace_file = found

    lines = trace_file.read_text(encoding="utf-8").strip().split("\n")
    updated = False
    new_lines = []

    for line in lines:
        if not line.strip():
            continue
        trace = json.loads(line)
        if trace["trace_id"] == trace_id:
            for key, value in updates.items():
                trace[key] = value
            updated = True
        new_lines.append(json.dumps(trace, ensure_ascii=False))

    if updated:
        trace_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return updated


def _find_trace_file(trace_id):
    # type: (str) -> Optional[Path]
    """在所有 trace 文件中查找包含指定 trace_id 的文件"""
    if not TRACES_DIR.exists():
        return None

    for f in sorted(TRACES_DIR.glob("traces-*.jsonl"), reverse=True):
        content = f.read_text(encoding="utf-8")
        if trace_id in content:
            return f

    return None


def _load_all_traces():
    # type: () -> List[Dict]
    """从所有 JSONL 文件加载全部 trace"""
    if not TRACES_DIR.exists():
        return []

    all_traces = []
    for f in sorted(TRACES_DIR.glob("traces-*.jsonl")):
        text = f.read_text(encoding="utf-8").strip()
        if not text:
            continue
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                all_traces.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return all_traces
