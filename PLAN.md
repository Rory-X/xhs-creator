# PLAN.md — xhs-creator v2.0 实现计划

> 基于 PRD.md，结合现有代码结构制定的详细实施方案

---

## 现有代码盘点

| 文件 | 行数 | 关键函数/类 | 修改需求 |
|------|------|-------------|----------|
| `cli.py` | 43 | `cli()` Click group | 注册新命令 |
| `llm.py` | 194 | `call_llm()`, `parse_llm_json()`, `_strip_think_tags()` | 集成 tracker，增加 track/command/options 参数 |
| `prompts.py` | 111 | 4 个 `*_SYSTEM_PROMPT` 常量, `LENGTH_DESC` | 增加 `get_prompt()` 函数支持版本化加载 |
| `config.py` | 130 | `load_config()`, `save_config()`, `DEFAULT_CONFIG` | 扩展默认配置项 |
| `formatter.py` | 207 | `format_*()` 系列 | 新增 `format_history()`, `format_stats()`, `format_recommendations()` 等 |
| `xhs_client.py` | 193 | `search_notes()`, `publish_note()` 等 | 无修改（Recommender 通过此模块采集趋势） |
| `commands/topic.py` | 106 | `topic()` | 集成 tracker，增加 `--no-track`, `--smart` |
| `commands/title.py` | 59 | `title()` | 集成 tracker，增加 `--no-track` |
| `commands/write.py` | 86 | `write()` | 集成 tracker，增加 `--no-track`, `--prompt-version` |
| `commands/analyze.py` | 71 | `analyze()` | 集成 tracker |
| `commands/publish.py` | 300 | `publish()`, `_generate_cover()` | 自动标记 trace 为 published |

---

## Phase 1: Tracker 基础（系统一核心）

**目标**: 实现 trace 数据模型、JSONL 读写、call_llm 集成

### 1.1 新建 `xhs_creator/tracker.py`

```python
# --- 数据结构 ---

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
    return TRACES_DIR / ".last_trace_id"

def start_trace(
    command: str,
    query: str,
    options: Dict[str, Any],
    prompt_info: Dict[str, str],
) -> str:
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

def end_trace(
    trace_id: str,
    content: str,
    parsed: Optional[Any],
    model: str,
    tokens: Optional[Dict[str, int]],
    latency_ms: int,
) -> None:
    """更新已有 trace 的 response 字段"""

def add_feedback(
    trace_id: str,
    rating: Optional[int] = None,       # 1-5
    adopted: Optional[bool] = None,
    published: Optional[bool] = None,
    edit_distance: Optional[int] = None,
) -> bool:
    """更新 trace 的 feedback 字段，返回是否成功"""

def get_last_trace_id() -> Optional[str]:
    """读取最近一次 trace_id"""

def get_recent_traces(
    n: int = 10,
    command: Optional[str] = None,
    rated_only: bool = False,
) -> List[Dict]:
    """获取最近 N 条 trace"""

def load_traces(
    since: Optional[str] = None,   # ISO date "2026-01-01"
    until: Optional[str] = None,
    command: Optional[str] = None,
) -> List[Dict]:
    """加载指定范围的所有 trace"""
```

**JSONL 读写实现细节**:
- `start_trace`: 构造完整 trace dict（feedback 字段全 null），append 到 JSONL，同时写 `.last_trace_id`
- `end_trace` / `add_feedback`: 读取 JSONL → 找到 trace_id → 更新字段 → 重写文件（当月文件不会太大）
- `load_traces`: 按 since/until 确定需要读取哪些月份文件，逐行 json.loads，按条件过滤

### 1.2 修改 `xhs_creator/llm.py`

```python
# call_llm 新增参数
def call_llm(
    query: str,
    system_prompt: str,
    model: str = None,
    track: bool = True,          # 新增
    command: str = None,         # 新增: "topic"/"title"/"write"/"analyze"
    options: dict = None,        # 新增: 当前命令的参数
    prompt_info: dict = None,    # 新增: {"template_name": ..., "template_version": ...}
) -> dict:
    """
    返回值新增 "_trace_id" 字段
    """
    # --- 新增: 调用前 start_trace ---
    trace_id = None
    start_time = None
    if track:
        from .tracker import start_trace
        start_time = time.time()
        prompt_info = prompt_info or {}
        prompt_info["rendered"] = system_prompt[:500]  # 截断保存
        trace_id = start_trace(
            command=command or "unknown",
            query=query,
            options=options or {},
            prompt_info=prompt_info,
        )

    # ... 原有调用逻辑不变 ...

    # --- 新增: 调用后 end_trace ---
    if track and trace_id:
        from .tracker import end_trace
        latency = int((time.time() - start_time) * 1000)
        end_trace(
            trace_id=trace_id,
            content=data.get("content", ""),
            parsed=None,  # 由命令层解析后更新
            model=data.get("model", ""),
            tokens=data.get("usage"),
            latency_ms=latency,
        )

    data["_trace_id"] = trace_id
    return data
```

**改动要点**:
- `import time` 放到文件顶部
- 新参数全有默认值，**不破坏**现有调用方（analyze.py 等无需修改也能工作）
- `_trace_id` 作为内部字段传递，不影响现有 JSON 输出逻辑

### 1.3 修改现有命令传递 track 参数

每个命令文件的改动模式相同（以 `commands/write.py` 为例）:

```python
# write.py 改动（其他命令同理）

@click.option("--no-track", is_flag=True, help="本次不记录调用历史")

def write(..., no_track, ...):
    # ...构造 prompt...

    result = call_llm(
        topic, prompt,
        track=not no_track,
        command="write",
        options={"style": style, "tone": tone, "length": length, "tags": tags},
        prompt_info={"template_name": "WRITE_SYSTEM_PROMPT", "template_version": "builtin"},
    )
```

**需修改的文件和新增选项**:
| 文件 | 新增 Click option | call_llm 新参数 |
|------|-------------------|-----------------|
| `commands/topic.py` | `--no-track` | `command="topic"`, `options={style, count}` |
| `commands/title.py` | `--no-track` | `command="title"`, `options={style, emoji, max_len}` |
| `commands/write.py` | `--no-track` | `command="write"`, `options={style, tone, length, tags}` |
| `commands/analyze.py` | `--no-track` | `command="analyze"`, `options={keyword, limit}` |

### 1.4 测试用例

```
test_tracker_generate_id       - trace_id 格式正确 (tr_YYYYMMDD_HHMMSS_6hex)
test_tracker_start_end         - start_trace 写入 JSONL，end_trace 更新 response
test_tracker_feedback          - add_feedback 更新 rating/adopted/published
test_tracker_last_id           - get_last_trace_id 返回最近写入的 id
test_tracker_recent            - get_recent_traces 按 n/command/rated_only 过滤
test_tracker_load_range        - load_traces 按 since/until 跨月加载
test_tracker_file_not_exist    - JSONL 文件不存在时返回空列表
test_llm_call_with_track       - call_llm(track=True) 返回 _trace_id
test_llm_call_no_track         - call_llm(track=False) 返回 _trace_id=None
```

### 1.5 依赖

- 无外部依赖
- 仅使用标准库: `json`, `time`, `uuid`, `pathlib`

---

## Phase 2: 反馈收集（rate + history 命令）

**目标**: 用户可评分、查看历史

### 2.1 新建 `xhs_creator/commands/rate.py`

```python
import click
from ..tracker import add_feedback, get_last_trace_id

@click.command()
@click.argument("score", type=int, required=False, default=None)
@click.option("--adopt", is_flag=True, help="标记为采用")
@click.option("--drop", is_flag=True, help="标记为废弃")
@click.option("--trace", "trace_id", default=None, help="指定 trace_id")
def rate(score, adopt, drop, trace_id):
    """对最近一次生成结果评分 (1-5)"""
    # 1. 确定 trace_id
    if not trace_id:
        trace_id = get_last_trace_id()
        if not trace_id:
            click.echo(click.style("没有找到最近的调用记录", fg="red"), err=True)
            raise SystemExit(1)

    # 2. 验证 score
    if score is not None and not (1 <= score <= 5):
        click.echo(click.style("评分范围: 1-5", fg="red"), err=True)
        raise SystemExit(1)

    # 3. 确定 adopted
    adopted = None
    if adopt:
        adopted = True
    elif drop:
        adopted = False

    # 4. 更新
    ok = add_feedback(trace_id, rating=score, adopted=adopted)
    if not ok:
        click.echo(click.style(f"未找到 trace: {trace_id}", fg="red"), err=True)
        raise SystemExit(1)

    # 5. 输出确认
    parts = []
    if score:
        parts.append(f"评分 {'⭐' * score}")
    if adopted is True:
        parts.append("已采用")
    elif adopted is False:
        parts.append("已废弃")
    click.echo(click.style(f"已更新: {' | '.join(parts)} ({trace_id})", fg="green"))
```

### 2.2 新建 `xhs_creator/commands/history_cmd.py`

```python
import click
from ..formatter import output_json
from ..tracker import get_recent_traces

@click.command("history")
@click.option("-n", "--count", default=10, help="显示条数")
@click.option("--command", "cmd_filter", default=None, help="按命令过滤")
@click.option("--rated", is_flag=True, help="只看已评分记录")
@click.option("--json", "json_mode", is_flag=True, help="JSON 输出")
def history(count, cmd_filter, rated, json_mode):
    """查看最近的调用历史"""
    traces = get_recent_traces(n=count, command=cmd_filter, rated_only=rated)

    if json_mode:
        output_json(traces)
        return

    if not traces:
        click.echo("暂无调用记录")
        return

    # 表格化输出
    for t in traces:
        _format_trace_row(t)

def _format_trace_row(trace: dict):
    """单行格式化一条 trace"""
    # trace_id | command | query[:30] | rating | timestamp
    ...
```

### 2.3 新增 `formatter.py` 函数

```python
def format_trace_row(trace: dict):
    """格式化单条 trace 为终端行"""
    # trace_id 截短显示（后8位）
    # command 用彩色标签
    # query 截断到 30 字
    # rating 用星号
    # timestamp 友好格式

def format_history_table(traces: list):
    """格式化 trace 列表为表格"""
```

### 2.4 修改 `cli.py` 注册新命令

```python
from .commands.rate import rate
from .commands.history_cmd import history

cli.add_command(rate)
cli.add_command(history)
```

### 2.5 测试用例

```
test_rate_last_trace          - 无参数 rate 5 更新最近 trace
test_rate_specific_trace      - --trace 指定 id 更新
test_rate_adopt               - --adopt 标记
test_rate_drop                - --drop 标记
test_rate_invalid_score       - score=6 报错
test_rate_no_trace            - 无历史时报错
test_history_default          - 默认返回 10 条
test_history_filter_command   - --command write 只返回 write
test_history_rated_only       - --rated 只返回有评分的
test_history_json             - --json 输出合法 JSON
```

### 2.6 依赖

- **Phase 1** (tracker.py 必须先完成)

---

## Phase 3: 统计分析（Analyzer + stats 命令）

**目标**: 按维度交叉分析 trace 数据，找到高效参数组合

### 3.1 新建 `xhs_creator/analyzer.py`

```python
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

# --- 数据结构 ---
# AnalysisReport: 完整分析报告 dict（见 PRD 3.4 数据模型）
# Combination: {"style": ..., "tone": ..., "length": ..., "avg_rating": ..., "count": ...}

def compute_stats(traces: List[Dict]) -> Dict:
    """
    计算基础统计:
    - total_traces, rated_traces, avg_rating, adopt_rate, publish_rate
    - by_command: {command: {count, avg_rating, adopt_rate}}
    """

def find_top_combinations(
    traces: List[Dict],
    top_k: int = 5,
    min_count: int = 3,
) -> List[Dict]:
    """
    交叉分析 style x tone x length → avg_rating
    只返回 count >= min_count 的组合
    按 avg_rating 降序取 top_k

    实现:
    1. 从 trace.input.options 提取 style, tone, length
    2. 以 (style, tone, length) 为 key 分组
    3. 计算每组 avg(feedback.rating)
    4. 排序返回
    """

def find_worst_combinations(
    traces: List[Dict],
    bottom_k: int = 3,
    min_count: int = 3,
) -> List[Dict]:
    """与 find_top_combinations 相反，取最低评分"""

def compare_prompt_versions(
    traces: List[Dict],
    template_name: str,
) -> Dict:
    """
    按 prompt.template_version 分组，对比不同版本的 avg_rating
    返回: {version: {count, avg_rating, adopt_rate}}
    """

def generate_report(
    since: Optional[str] = None,
    until: Optional[str] = None,
    command: Optional[str] = None,
) -> Dict:
    """
    生成完整分析报告:
    1. load_traces(since, until, command)
    2. compute_stats
    3. find_top/worst_combinations
    4. 组装 AnalysisReport dict
    """
```

### 3.2 新建 `xhs_creator/commands/stats.py`

```python
import click
from ..analyzer import generate_report
from ..formatter import output_json

@click.command()
@click.option("--command", "cmd_filter", default=None, help="按命令过滤")
@click.option("--since", default=None, help="起始日期 (YYYY-MM-DD)")
@click.option("--last", "last_period", default=None, help="最近时段 (如 30d)")
@click.option("--json", "json_mode", is_flag=True, help="JSON 输出")
def stats(cmd_filter, since, last_period, json_mode):
    """查看创作统计和参数分析"""
    # 解析 --last 为 since 日期
    if last_period:
        since = _parse_last_period(last_period)

    report = generate_report(since=since, command=cmd_filter)

    if json_mode:
        output_json(report)
    else:
        format_stats_report(report)

def _parse_last_period(period: str) -> str:
    """'30d' → ISO date 30 天前"""
    import re
    from datetime import datetime, timedelta
    match = re.match(r"(\d+)d", period)
    if match:
        days = int(match.group(1))
        return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return None
```

### 3.3 新增 `formatter.py` 函数

```python
def format_stats_report(report: dict):
    """
    格式化统计报告:
    - 总览: 调用次数 / 平均评分 / 采用率 / 发布率
    - 按命令分组表格
    - Top 参数组合（表格 + 星级）
    - Worst 参数组合
    - 优化建议列表
    """
```

### 3.4 注册命令

```python
# cli.py
from .commands.stats import stats
cli.add_command(stats)
```

### 3.5 测试用例

```
test_compute_stats_empty         - 空列表返回零值
test_compute_stats_basic         - 正确计算 avg_rating, adopt_rate
test_compute_stats_by_command    - by_command 分组正确
test_top_combinations            - 返回按 avg_rating 降序
test_top_combinations_min_count  - count < min_count 的组合被过滤
test_worst_combinations          - 返回最低评分组合
test_compare_versions            - 按 template_version 分组对比
test_generate_report             - 完整报告结构验证
test_parse_last_period           - "30d" → 正确日期
test_stats_command_json          - --json 输出合法
```

### 3.6 依赖

- **Phase 1** (tracker.load_traces)

---

## Phase 4: Prompt 版本管理

**目标**: prompt 版本化存储、查看、回滚

### 4.1 新建 `xhs_creator/optimizer.py`

```python
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

PROMPT_VERSIONS_DIR = Path.home() / ".xhs-creator" / "prompt_versions"

# 内置模板名到 prompts.py 常量的映射
TEMPLATE_NAMES = [
    "TOPIC_SYSTEM_PROMPT",
    "TITLE_SYSTEM_PROMPT",
    "WRITE_SYSTEM_PROMPT",
    "ANALYZE_SYSTEM_PROMPT",
]

def _template_dir(template_name: str) -> Path:
    """返回模板版本目录，如 ~/.xhs-creator/prompt_versions/WRITE_SYSTEM_PROMPT/"""
    d = PROMPT_VERSIONS_DIR / template_name
    d.mkdir(parents=True, exist_ok=True)
    return d

def _get_current_version(template_name: str) -> Optional[str]:
    """读取 current 文件获取当前版本号"""
    current_file = _template_dir(template_name) / "current"
    if current_file.exists():
        return current_file.read_text().strip()
    return None

def get_current_prompt(template_name: str) -> Optional[str]:
    """
    获取当前生效的 prompt 内容
    返回 None 时 fallback 到内置模板
    """
    version = _get_current_version(template_name)
    if not version:
        return None
    return get_prompt_by_version(template_name, version)

def get_prompt_by_version(template_name: str, version: str) -> Optional[str]:
    """读取指定版本的 prompt 内容"""
    version_file = _template_dir(template_name) / f"{version}.json"
    if not version_file.exists():
        return None
    data = json.loads(version_file.read_text(encoding="utf-8"))
    return data.get("content")

def list_versions(template_name: str) -> List[Dict]:
    """
    列出所有版本，按创建时间倒序
    每条: {version, created_at, change_summary, is_current}
    """

def save_version(
    template_name: str,
    content: str,
    change_summary: str,
    change_reason: str,         # "manual" | "analyzer_auto" | "user_edit"
    metrics: Optional[Dict] = None,
) -> str:
    """
    保存新版本:
    1. 读取当前版本号 → 计算下一版本号 (v1, v2, ...)
    2. 写入 {version}.json（含 content, metadata）
    3. 更新 current 文件
    返回新版本号
    """

def rollback(template_name: str, target_version: Optional[str] = None) -> str:
    """
    回滚:
    - target_version 指定时回滚到该版本
    - 未指定时回滚到 parent_version
    更新 current 文件
    返回回滚到的版本号
    """

def reset_to_default(template_name: str) -> None:
    """删除 current 文件 → get_current_prompt 返回 None → fallback 到内置"""

# --- Phase 5 实现（占位）---

def suggest_optimization(
    template_name: str,
    report: Dict,
) -> List[Dict]:
    """
    基于分析报告，调用 LLM 生成优化建议
    每条: {modification, reason, expected_effect}
    """
    ...

def apply_optimization(
    template_name: str,
    suggestion: Dict,
) -> str:
    """应用优化建议，保存为新版本"""
    ...
```

### 4.2 修改 `xhs_creator/prompts.py`

```python
# 新增: 内置模板注册表
BUILTIN_PROMPTS = {
    "TOPIC_SYSTEM_PROMPT": TOPIC_SYSTEM_PROMPT,
    "TITLE_SYSTEM_PROMPT": TITLE_SYSTEM_PROMPT,
    "WRITE_SYSTEM_PROMPT": WRITE_SYSTEM_PROMPT,
    "ANALYZE_SYSTEM_PROMPT": ANALYZE_SYSTEM_PROMPT,
}

def get_prompt(template_name: str, version: Optional[str] = None, **kwargs) -> str:
    """
    加载 prompt 模板:
    1. 指定 version → optimizer.get_prompt_by_version
    2. 未指定 → optimizer.get_current_prompt
    3. 都返回 None → BUILTIN_PROMPTS fallback
    4. .format(**kwargs) 渲染
    """
    from .optimizer import get_current_prompt, get_prompt_by_version

    content = None
    if version:
        content = get_prompt_by_version(template_name, version)
    else:
        content = get_current_prompt(template_name)

    if content is None:
        content = BUILTIN_PROMPTS.get(template_name)

    if content is None:
        raise ValueError(f"Unknown template: {template_name}")

    return content.format(**kwargs) if kwargs else content
```

### 4.3 新建 `xhs_creator/commands/prompt_cmd.py`

```python
import click
from ..optimizer import (
    get_current_prompt, list_versions, rollback, reset_to_default,
    TEMPLATE_NAMES,
)
from ..prompts import BUILTIN_PROMPTS, get_prompt
from ..formatter import output_json

# 命令名到模板名映射
CMD_TO_TEMPLATE = {
    "topic": "TOPIC_SYSTEM_PROMPT",
    "title": "TITLE_SYSTEM_PROMPT",
    "write": "WRITE_SYSTEM_PROMPT",
    "analyze": "ANALYZE_SYSTEM_PROMPT",
}

@click.group("prompt")
def prompt_group():
    """管理 Prompt 模板"""
    pass

@prompt_group.command("show")
@click.argument("command_name", type=click.Choice(["topic", "title", "write", "analyze"]))
def show(command_name):
    """查看当前 prompt 模板"""
    template = CMD_TO_TEMPLATE[command_name]
    content = get_current_prompt(template)
    source = "自定义版本"
    if content is None:
        content = BUILTIN_PROMPTS[template]
        source = "内置默认"
    click.echo(click.style(f"\n[{command_name}] prompt ({source}):\n", fg="cyan", bold=True))
    click.echo(content)

@prompt_group.command("versions")
@click.argument("command_name", type=click.Choice(["topic", "title", "write", "analyze"]))
def versions(command_name):
    """查看 prompt 版本历史"""
    template = CMD_TO_TEMPLATE[command_name]
    vers = list_versions(template)
    if not vers:
        click.echo("暂无版本历史（使用内置默认）")
        return
    for v in vers:
        marker = " (当前)" if v.get("is_current") else ""
        click.echo(f"  {v['version']}{marker}  {v['created_at']}  {v.get('change_summary', '')}")

@prompt_group.command("rollback")
@click.argument("command_name", type=click.Choice(["topic", "title", "write", "analyze"]))
@click.argument("version", required=False, default=None)
def rollback_cmd(command_name, version):
    """回滚到上一版本或指定版本"""
    template = CMD_TO_TEMPLATE[command_name]
    result = rollback(template, version)
    click.echo(click.style(f"已回滚到 {result}", fg="green"))

@prompt_group.command("reset")
@click.argument("command_name", type=click.Choice(["topic", "title", "write", "analyze"]))
@click.confirmation_option(prompt="确定恢复为内置默认 prompt？")
def reset(command_name):
    """恢复为内置默认 prompt"""
    template = CMD_TO_TEMPLATE[command_name]
    reset_to_default(template)
    click.echo(click.style("已恢复为内置默认", fg="green"))

@prompt_group.command("optimize")
@click.argument("command_name", type=click.Choice(["topic", "title", "write", "analyze"]), required=False)
def optimize(command_name):
    """分析数据并生成优化建议（Phase 5 实现）"""
    click.echo("此功能将在后续版本实现")

@prompt_group.command("apply")
@click.argument("command_name", type=click.Choice(["topic", "title", "write", "analyze"]))
def apply_cmd(command_name):
    """应用最新优化建议（Phase 5 实现）"""
    click.echo("此功能将在后续版本实现")
```

### 4.4 修改命令使用 `get_prompt` 加载

以 `commands/write.py` 为例:

```python
# 之前:
from ..prompts import LENGTH_DESC, WRITE_SYSTEM_PROMPT
prompt = WRITE_SYSTEM_PROMPT.format(...)

# 之后:
from ..prompts import LENGTH_DESC, get_prompt

@click.option("--prompt-version", default=None, help="使用指定版本 prompt")

def write(..., prompt_version, ...):
    prompt = get_prompt("WRITE_SYSTEM_PROMPT", version=prompt_version,
                        style=style, tone=tone, length_desc=length_desc,
                        tags_instruction=tags_instruction,
                        image_tips_instruction=image_tips_instruction)
```

**需修改的命令文件**: `topic.py`, `title.py`, `write.py`, `analyze.py` — 将直接引用常量改为调用 `get_prompt()`

### 4.5 注册命令

```python
# cli.py
from .commands.prompt_cmd import prompt_group
cli.add_command(prompt_group)
```

### 4.6 测试用例

```
test_save_version_first        - 首次保存生成 v1
test_save_version_increment    - 连续保存生成 v1, v2, v3
test_get_current_prompt        - 返回最新版本内容
test_get_current_no_version    - 无版本时返回 None
test_get_by_version            - 指定版本返回正确内容
test_list_versions             - 按时间倒序，is_current 标记正确
test_rollback_to_previous      - 回滚到上一版本
test_rollback_to_specific      - 回滚到指定版本 v1
test_reset_to_default          - 重置后 get_current 返回 None
test_get_prompt_fallback       - 无自定义版本时 fallback 到内置
test_get_prompt_with_version   - 指定版本加载正确
test_get_prompt_format         - format kwargs 正确渲染
```

### 4.7 依赖

- 无（可与 Phase 1-3 并行开发）
- 但 `get_prompt()` 需在命令中使用时，与 Phase 1 的 tracker 集成一起改

---

## Phase 5: 自动优化（Optimizer LLM 分析）

**目标**: 基于 Analyzer 结论调用 LLM 生成 prompt 优化建议

### 5.1 完善 `xhs_creator/optimizer.py`

```python
# 新增 prompt 模板
OPTIMIZE_SYSTEM_PROMPT = """你是 prompt engineering 专家。
以下是一个用于生成小红书{command_type}内容的 system prompt 模板：

--- 当前 Prompt ---
{current_prompt}
--- 结束 ---

以下是该 prompt 的历史使用数据分析：
{analysis_report}

高分参数组合（用户最满意的配置）：
{top_combinations}

低分参数组合（用户最不满意的配置）：
{worst_combinations}

请基于以上数据分析，给出 prompt 优化建议。

返回 JSON 格式：
{{
  "suggestions": [
    {{
      "modification": "具体修改内容",
      "reason": "修改理由（基于数据支撑）",
      "expected_effect": "预期效果"
    }}
  ],
  "optimized_prompt": "完整的优化后 prompt 模板（保持原有的 {{变量名}} 占位符）"
}}"""

def suggest_optimization(
    template_name: str,
    report: Dict,
) -> Dict:
    """
    1. 从 optimizer 获取当前 prompt（或 fallback 到内置）
    2. 格式化分析报告为文本
    3. 调用 call_llm（使用 OPTIMIZE_SYSTEM_PROMPT）
    4. 解析返回的 suggestions + optimized_prompt
    5. 返回结构化建议
    """

def apply_optimization(
    template_name: str,
    optimized_prompt: str,
    change_summary: str,
    metrics: Dict,
) -> str:
    """
    将优化后的 prompt 保存为新版本
    调用 save_version()
    """
```

### 5.2 完善 `commands/prompt_cmd.py` 的 optimize 和 apply 命令

```python
@prompt_group.command("optimize")
@click.argument("command_name", type=click.Choice(["topic", "title", "write", "analyze"]), required=False)
@click.option("--since", default=None, help="分析起始日期")
@click.option("--last", "last_period", default=None, help="最近时段 (如 30d)")
def optimize(command_name, since, last_period):
    """分析数据并生成优化建议"""
    # 1. 确定要优化的模板（未指定则优化所有）
    # 2. 调用 analyzer.generate_report
    # 3. 调用 optimizer.suggest_optimization
    # 4. 格式化输出建议
    # 5. 将建议缓存到 ~/.xhs-creator/prompt_versions/{template}/.pending_suggestion.json

@prompt_group.command("apply")
@click.argument("command_name", type=click.Choice(["topic", "title", "write", "analyze"]))
@click.confirmation_option(prompt="确定应用优化建议？")
def apply_cmd(command_name):
    """应用最新优化建议"""
    # 1. 读取 .pending_suggestion.json
    # 2. 调用 optimizer.apply_optimization
    # 3. 输出新版本号和变更摘要
```

### 5.3 高分 trace 作为 few-shot（P2）

```python
def inject_few_shot(template_name: str, prompt: str, traces: List[Dict], top_n: int = 2) -> str:
    """
    从 traces 中选取评分最高的 top_n 条作为示例注入 prompt
    在 prompt 末尾追加:

    以下是优质输出示例：
    示例1: {high_rated_trace.response.content[:500]}
    示例2: ...
    """
```

### 5.4 测试用例

```
test_suggest_optimization_format   - 返回包含 suggestions 和 optimized_prompt
test_apply_optimization            - 保存新版本，current 更新
test_optimize_command_output       - CLI 输出格式正确
test_apply_from_pending            - 从缓存建议应用
test_inject_few_shot               - 正确注入高分示例
test_optimize_with_empty_data      - 无评分数据时提示不足
```

### 5.5 依赖

- **Phase 3** (analyzer.generate_report)
- **Phase 4** (optimizer 版本管理)

---

## Phase 6: 闭环集成（publish 标记 + edit_distance + 自动触发）

**目标**: 自动化反馈收集，闭合优化环路

### 6.1 修改 `commands/publish.py`

```python
def publish(...):
    # ... 发布成功后 ...

    # 自动标记最近的 write trace 为 published
    from ..tracker import add_feedback, get_last_trace_id
    last_id = get_last_trace_id()
    if last_id:
        add_feedback(last_id, published=True)
```

### 6.2 新增 edit_distance 计算（P2）

```python
# tracker.py 新增
def compute_edit_distance(original: str, edited: str) -> int:
    """简化的编辑距离：字符级差异数 / max(len) * 100"""
    # 使用 difflib.SequenceMatcher 而非完整 Levenshtein
    from difflib import SequenceMatcher
    ratio = SequenceMatcher(None, original, edited).ratio()
    return int((1 - ratio) * 100)
```

如果用户在 publish 时的 content 与最近 write trace 的 response.content 不同，自动计算 edit_distance 并记录。

### 6.3 自动触发优化（P2）

```python
# tracker.py 新增
def check_auto_optimize_threshold() -> Optional[str]:
    """
    检查是否达到自动优化阈值
    读取 config.yaml 的 prompt_optimization.auto_optimize_threshold
    统计自上次优化以来的新评分数量
    返回需要优化的 template_name 或 None
    """
```

在 `add_feedback` 中调用，达到阈值后提示用户或自动执行。

### 6.4 测试用例

```
test_publish_marks_trace       - 发布成功后最近 trace 标记 published=true
test_edit_distance_same        - 相同内容 → 0
test_edit_distance_different   - 不同内容 → 合理百分比
test_auto_optimize_threshold   - 达到阈值返回 template_name
test_auto_optimize_below       - 未达阈值返回 None
```

### 6.5 依赖

- **Phase 2** (feedback)
- **Phase 5** (optimizer)

---

## Phase 7: TrendCollector（系统二基础）

**目标**: 从小红书采集热门话题数据并缓存

### 7.1 新建 `xhs_creator/recommender/__init__.py`

```python
"""智能话题推荐系统"""
```

### 7.2 新建 `xhs_creator/recommender/trends.py`

```python
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
}}"""

def _cache_path(domain: str) -> Path:
    """趋势缓存文件路径"""
    TRENDS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    return TRENDS_DIR / f"trends-{domain}-{date_str}.json"

def is_cache_valid(domain: str) -> bool:
    """检查缓存是否在 TTL 内"""
    path = _cache_path(domain)
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    collected_at = data.get("collected_at", "")
    ttl_hours = data.get("ttl_hours", 6)
    # 解析时间判断是否过期
    ...

def get_cached_trends(domain: str) -> Optional[Dict]:
    """读取缓存的趋势数据"""
    path = _cache_path(domain)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def collect_trends(domains: List[str], force_refresh: bool = False) -> Dict[str, Dict]:
    """
    采集多个领域的趋势数据

    实现:
    1. 遍历 domains
    2. is_cache_valid → 用缓存
    3. 否则: search_notes(domain) → LLM 提取结构化趋势 → 缓存
    4. MCP 不可用时返回空（降级）

    Returns: {domain: TrendData}
    """

def refresh_trends(domain: str) -> Optional[Dict]:
    """强制刷新单个领域的趋势"""
    return collect_trends([domain], force_refresh=True).get(domain)
```

### 7.3 测试用例

```
test_cache_path_format         - 路径包含 domain 和日期
test_cache_valid_fresh         - 刚写入的缓存有效
test_cache_valid_expired       - 超 TTL 的缓存无效
test_collect_with_cache        - 缓存有效时不调用 MCP
test_collect_force_refresh     - force_refresh=True 忽略缓存
test_collect_mcp_unavailable   - MCP 不可用时返回空 dict
test_trend_extract_prompt      - LLM 解析返回合法结构
```

### 7.4 依赖

- `xhs_client.py` (search_notes)
- `llm.py` (call_llm)

---

## Phase 8: UserProfile（用户画像）

**目标**: 构建和维护用户兴趣画像

### 8.1 新建 `xhs_creator/recommender/profile.py`

```python
import yaml
from pathlib import Path
from typing import Dict, List, Optional

from ..config import load_config
from ..tracker import load_traces

PROFILE_PATH = Path.home() / ".xhs-creator" / "profile.yaml"

def load_profile() -> Dict:
    """加载用户画像，不存在则返回空画像结构"""
    if PROFILE_PATH.exists():
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or _empty_profile()
    return _empty_profile()

def _empty_profile() -> Dict:
    return {
        "interests": {"primary": "", "domains": {}},
        "style_preference": {"preferred": [], "avoid": []},
        "created_topics": [],
        "feedback_history": {"liked_recommendations": [], "disliked_recommendations": []},
        "updated_at": None,
    }

def save_profile(profile: Dict) -> None:
    """保存画像到 YAML"""

def build_profile(force_rebuild: bool = False) -> Dict:
    """
    从 config + traces 构建/更新画像:
    1. config.domains → interests.domains (source: "config")
    2. traces → 统计高分领域/风格 → interests.domains (source: "history")
    3. traces → 提取已创作 topic → created_topics
    4. 合并权重（config 0.5 + history 动态）
    5. save_profile
    """

def get_created_topics() -> List[str]:
    """从画像中获取已创作话题列表"""

def update_from_feedback(rec_id: str, liked: bool) -> None:
    """根据推荐反馈更新画像"""

def add_domain(domain: str) -> None:
    """手动添加兴趣领域"""

def remove_domain(domain: str) -> None:
    """手动移除兴趣领域"""
```

### 8.2 新建 `xhs_creator/commands/profile_cmd.py`

```python
import click
from ..recommender.profile import (
    load_profile, build_profile, add_domain, remove_domain,
)
from ..formatter import output_json

@click.group("profile")
def profile_group():
    """管理用户兴趣画像"""
    pass

@profile_group.command("show")
@click.option("--json", "json_mode", is_flag=True)
def show(json_mode):
    """查看当前画像"""
    profile = load_profile()
    if json_mode:
        output_json(profile)
    else:
        _format_profile(profile)

@profile_group.command("refresh")
def refresh():
    """基于最新数据重建画像"""
    profile = build_profile(force_rebuild=True)
    click.echo(click.style("画像已更新", fg="green"))

@profile_group.command("add-domain")
@click.argument("domain")
def add_domain_cmd(domain):
    """添加感兴趣领域"""
    add_domain(domain)
    click.echo(click.style(f"已添加: {domain}", fg="green"))

@profile_group.command("remove-domain")
@click.argument("domain")
def remove_domain_cmd(domain):
    """移除领域"""
    remove_domain(domain)
    click.echo(click.style(f"已移除: {domain}", fg="green"))
```

### 8.3 注册命令

```python
# cli.py
from .commands.profile_cmd import profile_group
cli.add_command(profile_group)
```

### 8.4 测试用例

```
test_empty_profile             - 无文件时返回空结构
test_build_from_config         - config.domains 正确导入
test_build_from_traces         - traces 中的高分领域提取
test_created_topics            - 从 traces 提取已创作 topic
test_update_feedback_like      - liked 更新 feedback_history
test_update_feedback_dislike   - disliked 更新
test_add_domain                - 新增领域
test_remove_domain             - 移除领域
test_save_load_roundtrip       - 保存后加载一致
```

### 8.5 依赖

- **Phase 1** (tracker.load_traces — 用于 build_profile 中提取历史数据)

---

## Phase 9: 推荐引擎 MVP + 评分

**目标**: LLM 生成候选话题 + 多维评分 + recommend 命令

### 9.1 新建 `xhs_creator/recommender/scorer.py`

```python
from typing import Dict, List

def score_topic(
    topic: Dict,
    profile: Dict,
    trends: Dict,
    calendar_events: List[Dict],
    weights: Dict = None,
) -> Dict:
    """
    综合评分:
    - trend_score = compute_trend_score(topic, trends)
    - match_score = compute_match_score(topic, profile)
    - freshness_score = compute_freshness(topic, profile.created_topics)
    - timeliness_score = compute_timeliness(topic, calendar_events)
    - final_score = weighted sum

    返回 topic dict 增加 *_score 和 final_score 字段
    """

def compute_trend_score(topic: Dict, trends: Dict) -> float:
    """
    话题在趋势中的热度 (0-1)
    用关键词匹配: topic.topic vs trends.hot_keywords/hot_tags
    匹配越多分越高
    """

def compute_match_score(topic: Dict, profile: Dict) -> float:
    """
    话题与用户兴趣的匹配度 (0-1)
    用关键词重叠: topic.tags vs profile.interests.domains
    """

def compute_freshness(topic: Dict, created_topics: List[str]) -> float:
    """
    新鲜度 (0-1): 与已创作话题的相似度取反
    用简单关键词重叠（非 embedding）:
    1. 分词（按字符 bigram 或空格分词）
    2. 计算 jaccard 相似度
    3. 1 - max_similarity
    """

def compute_timeliness(topic: Dict, calendar_events: List[Dict]) -> float:
    """
    时效性 (0-1): 话题与当前时间因素的关联
    topic.tags 与 calendar_events.boost_tags 的重叠
    """

def rank_topics(topics: List[Dict], weights: Dict = None) -> List[Dict]:
    """按 final_score 降序排序"""
```

### 9.2 新建 `xhs_creator/recommender/calendar.py`

```python
from datetime import datetime
from typing import Dict, List

# 内置日历事件（硬编码）
CALENDAR_EVENTS = [
    {"month": 1, "day_range": (1, 3), "name": "元旦", "boost_tags": ["新年", "跨年", "年度总结"]},
    {"month": 2, "day_range": (14, 14), "name": "情人节", "boost_tags": ["情人节", "礼物", "约会"]},
    {"month": 3, "day_range": (8, 8), "name": "妇女节", "boost_tags": ["女性", "独立", "自我提升"]},
    {"month": 5, "day_range": (1, 3), "name": "劳动节", "boost_tags": ["旅行", "假期", "出行"]},
    {"month": 6, "day_range": (18, 18), "name": "618", "boost_tags": ["购物", "好物推荐", "优惠"]},
    {"month": 9, "day_range": (1, 3), "name": "开学季", "boost_tags": ["开学", "学习", "文具"]},
    {"month": 11, "day_range": (11, 11), "name": "双十一", "boost_tags": ["购物", "好物", "囤货"]},
    {"month": 12, "day_range": (25, 25), "name": "圣诞", "boost_tags": ["圣诞", "礼物", "节日"]},
    # 季节
    {"season": "spring", "months": [3, 4, 5], "name": "春季", "boost_tags": ["春游", "换季", "踏青"]},
    {"season": "summer", "months": [6, 7, 8], "name": "夏季", "boost_tags": ["防晒", "夏日", "清凉"]},
    {"season": "autumn", "months": [9, 10, 11], "name": "秋季", "boost_tags": ["秋天", "秋冬", "穿搭"]},
    {"season": "winter", "months": [12, 1, 2], "name": "冬季", "boost_tags": ["冬天", "保暖", "年味"]},
]

def get_current_events() -> List[Dict]:
    """返回当前日期命中的日历事件"""

def get_boost_tags() -> List[str]:
    """返回当前所有 boost_tags 合集"""
```

### 9.3 新建 `xhs_creator/recommender/engine.py`

```python
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..config import load_config
from ..llm import call_llm, parse_llm_json
from .trends import collect_trends
from .profile import load_profile, get_created_topics
from .scorer import score_topic, rank_topics
from .calendar import get_current_events, get_boost_tags

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
}}"""

class Recommender:
    def generate_recommendations(
        self,
        n: int = 5,
        domain: Optional[str] = None,
        explore: bool = False,
        refresh: bool = False,
    ) -> List[Dict]:
        """
        推荐主流程:
        1. load_profile()
        2. collect_trends(domains, force_refresh=refresh)
        3. get_current_events()
        4. 构造 prompt → call_llm → 生成 n*2 个候选
        5. score_topic 评分
        6. 去重（vs created_topics）
        7. explore → _inject_exploration()
        8. 取 top n，缓存结果
        """

    def get_cached_recommendations(self) -> Optional[List[Dict]]:
        """读取当日缓存的推荐结果"""

    def pick_recommendation(self, index: int) -> Optional[Dict]:
        """选择第 index 个推荐"""

    def feedback(self, rec_id: str, liked: bool) -> None:
        """对推荐点赞/踩"""
        from .profile import update_from_feedback
        update_from_feedback(rec_id, liked)

    def _is_novel(self, topic: Dict, created_topics: List[str]) -> bool:
        """检查话题是否与已创作内容重复"""
        # 用 scorer.compute_freshness 的逻辑

    def _inject_exploration(self, topics: List[Dict], ...) -> List[Dict]:
        """插入 1-2 个跨领域话题"""
```

### 9.4 新建 `xhs_creator/commands/recommend.py`

```python
import click
from ..recommender.engine import Recommender
from ..formatter import output_json

@click.group("recommend", invoke_without_command=True)
@click.option("-n", "--count", default=5, help="推荐数量")
@click.option("--domain", default=None, help="限定领域")
@click.option("--explore", is_flag=True, help="探索模式")
@click.option("--refresh", is_flag=True, help="强制刷新")
@click.option("--json", "json_mode", is_flag=True, help="JSON 输出")
@click.pass_context
def recommend(ctx, count, domain, explore, refresh, json_mode):
    """获取今日话题推荐"""
    if ctx.invoked_subcommand is not None:
        return

    engine = Recommender()

    # 检查缓存
    if not refresh:
        cached = engine.get_cached_recommendations()
        if cached and not json_mode:
            click.echo(click.style("(使用缓存，--refresh 可刷新)\n", fg="bright_black"))
            _display_recommendations(cached[:count])
            return

    recommendations = engine.generate_recommendations(n=count, domain=domain, explore=explore, refresh=refresh)

    if json_mode:
        output_json({"recommendations": recommendations})
    else:
        _display_recommendations(recommendations)

@recommend.command("pick")
@click.argument("index", type=int)
@click.option("--title", "gen_title", is_flag=True, help="直接生成标题")
@click.option("--write", "gen_write", is_flag=True, help="直接生成正文")
def pick(index, gen_title, gen_write):
    """选择推荐话题进入创作流程"""
    engine = Recommender()
    rec = engine.pick_recommendation(index)
    if not rec:
        click.echo(click.style(f"未找到第 {index} 条推荐", fg="red"), err=True)
        raise SystemExit(1)

    topic_text = rec["topic"]
    click.echo(click.style(f"已选择: {topic_text}", fg="green"))

    if gen_title:
        # 调用 title 命令
        from .title import title
        ctx = click.Context(title)
        ctx.invoke(title, text=topic_text)
    elif gen_write:
        # 调用 write 命令
        from .write import write
        ctx = click.Context(write)
        ctx.invoke(write, topic=topic_text)
    else:
        click.echo(f"\n可继续执行:")
        click.echo(f"  xhs-creator title \"{topic_text}\"")
        click.echo(f"  xhs-creator write -t \"{topic_text}\"")

@recommend.command("like")
@click.argument("index", type=int)
def like(index):
    """对推荐点赞"""
    engine = Recommender()
    rec = engine.pick_recommendation(index)
    if rec:
        engine.feedback(rec.get("id", f"rec_{index}"), liked=True)
        click.echo(click.style("已点赞", fg="green"))

@recommend.command("dislike")
@click.argument("index", type=int)
def dislike(index):
    """对推荐踩"""
    engine = Recommender()
    rec = engine.pick_recommendation(index)
    if rec:
        engine.feedback(rec.get("id", f"rec_{index}"), liked=False)
        click.echo(click.style("已标记不感兴趣", fg="yellow"))

def _display_recommendations(recs: list):
    """格式化输出推荐列表"""
    click.echo(click.style(f"\n💡 今日推荐 ({len(recs)} 条)\n", fg="cyan", bold=True))
    for i, rec in enumerate(recs, 1):
        heat = "🔥" * min(rec.get("heat_score", 0), 5)
        click.echo(click.style(f"  {i}. {rec['topic']}", fg="bright_white", bold=True))
        click.echo(f"     {heat}  风格: {rec.get('suggested_style', '-')}  语气: {rec.get('suggested_tone', '-')}")
        click.echo(f"     💬 {rec.get('reason', '')}")
        tags = rec.get("tags", [])
        if tags:
            click.echo(f"     {' '.join('#' + t for t in tags)}")
        click.echo()
```

### 9.5 注册命令

```python
# cli.py
from .commands.recommend import recommend
cli.add_command(recommend)
```

### 9.6 测试用例

```
test_compute_trend_score       - 热门关键词匹配评分
test_compute_match_score       - 用户兴趣匹配评分
test_compute_freshness         - 相似话题低分，新话题高分
test_compute_timeliness        - 节假日相关话题加分
test_rank_topics               - 按 final_score 正确排序
test_calendar_events_march     - 3月返回妇女节+春季事件
test_recommender_generate      - 完整推荐流程（mock LLM）
test_recommender_cache         - 缓存读写
test_recommender_dedup         - 已创作话题被过滤
test_pick_recommendation       - 正确返回指定索引
test_feedback_updates_profile  - 反馈更新画像
test_explore_mode              - 包含跨领域推荐
```

### 9.7 依赖

- **Phase 7** (trends.py)
- **Phase 8** (profile.py)

---

## Phase 10: trends 命令 + 配置扩展

**目标**: 独立趋势查看 + 统一配置

### 10.1 新建 `xhs_creator/commands/trends_cmd.py`

```python
import click
from ..recommender.trends import collect_trends, refresh_trends, get_cached_trends
from ..config import load_config
from ..formatter import output_json

@click.command("trends")
@click.argument("domain", required=False, default=None)
@click.option("--refresh", is_flag=True, help="强制刷新")
@click.option("--json", "json_mode", is_flag=True, help="JSON 输出")
def trends(domain, refresh, json_mode):
    """查看各领域当前趋势"""
    cfg = load_config()

    if domain:
        domains = [domain]
    else:
        # 使用配置的所有领域
        d = cfg.get("domains", {})
        domains = []
        if d.get("primary"):
            domains.append(d["primary"])
        domains.extend(d.get("secondary", []))
        domains.extend(cfg.get("recommend", {}).get("auto_collect_domains", []))

    if not domains:
        click.echo(click.style("未配置领域，请指定: xhs-creator trends \"AI\"", fg="yellow"))
        return

    all_trends = collect_trends(domains, force_refresh=refresh)

    if json_mode:
        output_json(all_trends)
    else:
        _format_trends(all_trends)

def _format_trends(all_trends: dict):
    """格式化趋势输出"""
    for domain, data in all_trends.items():
        click.echo(click.style(f"\n📈 {domain} 领域趋势", fg="cyan", bold=True))
        for topic in data.get("hot_topics", [])[:5]:
            trend_icon = {"rising": "📈", "stable": "➡️", "declining": "📉"}.get(topic.get("trend"), "")
            click.echo(f"  {trend_icon} {topic['keyword']}  提及 {topic.get('mention_count', '-')}次  均赞 {topic.get('avg_likes', '-')}")
        tags = data.get("hot_tags", [])
        if tags:
            click.echo(f"  热门标签: {' '.join('#' + t for t in tags[:8])}")
        click.echo()
```

### 10.2 修改 `config.py` 扩展默认配置

```python
# DEFAULT_CONFIG 新增:
"prompt_optimization": {
    "auto_optimize": False,
    "auto_optimize_threshold": 20,
    "optimization_model": None,
},
"recommend": {
    "enabled": True,
    "daily_count": 5,
    "cache_ttl_hours": 6,
    "weights": {
        "trend": 0.3,
        "match": 0.3,
        "freshness": 0.25,
        "timeliness": 0.15,
    },
    "explore_ratio": 0.2,
    "auto_collect_domains": [],
},
```

### 10.3 注册命令

```python
# cli.py
from .commands.trends_cmd import trends
cli.add_command(trends)
```

### 10.4 测试用例

```
test_trends_single_domain     - 单领域趋势查看
test_trends_multi_domain      - 多领域
test_trends_refresh           - 强制刷新
test_trends_no_domain         - 无配置时提示
test_config_new_keys          - 新配置项有默认值
test_config_merge_existing    - 不破坏现有配置
```

### 10.5 依赖

- **Phase 7** (trends.py)

---

## Phase 11: topic 命令集成推荐 + 最终集成

**目标**: 将推荐系统接入现有 topic 命令，完成跨系统集成

### 11.1 修改 `commands/topic.py`

```python
@click.option("--smart", is_flag=True, help="使用智能推荐引擎")

def topic(keyword, count, style, hot, smart, json_mode):
    # ... 无关键词且 smart 模式时 ...
    if not keyword and smart:
        from ..recommender.engine import Recommender
        engine = Recommender()
        recs = engine.generate_recommendations(n=count)
        # 将推荐结果转为 topic 格式输出
```

### 11.2 recommend pick 记录推荐来源到 trace

```python
# recommend.py pick 命令中
# 调用 write 时传递 source 信息
# trace.input 中增加 "source": "recommendation:rec_001"
```

### 11.3 RECOMMEND_SYSTEM_PROMPT 纳入版本管理

```python
# prompts.py
RECOMMEND_SYSTEM_PROMPT = "..."  # 新增推荐模板

BUILTIN_PROMPTS["RECOMMEND_SYSTEM_PROMPT"] = RECOMMEND_SYSTEM_PROMPT

# optimizer.py TEMPLATE_NAMES 增加
TEMPLATE_NAMES.append("RECOMMEND_SYSTEM_PROMPT")
```

### 11.4 测试用例

```
test_topic_smart_mode          - --smart 使用推荐引擎
test_recommend_source_in_trace - pick → write 的 trace 包含推荐来源
test_recommend_prompt_versioned - RECOMMEND 模板可版本化
```

### 11.5 依赖

- **Phase 9** (推荐引擎)
- **Phase 1** (tracker)
- **Phase 4** (prompt 版本管理)

---

## 实施总览

```
                    ┌──────────────────────┐
                    │  Phase 1: Tracker    │  ← 最先实施，两个系统的基础
                    │  tracker.py + llm.py │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌──────▼──────┐  ┌──────▼──────────┐
    │ Phase 2: 反馈  │ │ Phase 3:    │  │ Phase 4: Prompt  │ ← 可并行
    │ rate + history │ │ Analyzer +  │  │ 版本管理         │
    │                │ │ stats       │  │                  │
    └────────┬───────┘ └──────┬──────┘  └──────┬──────────┘
             │                │                │
             │         ┌──────▼──────┐         │
             │         │ Phase 5:    │◀────────┘
             │         │ 自动优化    │
             │         └──────┬──────┘
             │                │
             └────────┬───────┘
                      │
             ┌────────▼────────┐
             │ Phase 6: 闭环   │  ← 系统一完成
             │ publish+auto    │
             └─────────────────┘

    ┌─────────────────┐  ┌──────────────────┐
    │ Phase 7: Trends │  │ Phase 8: Profile │  ← 可并行
    │ 趋势采集+缓存   │  │ 用户画像          │
    └────────┬────────┘  └────────┬─────────┘
             │                    │
             └──────────┬─────────┘
                        │
             ┌──────────▼──────────┐
             │ Phase 9: 推荐 MVP   │
             │ engine + scorer +   │
             │ recommend 命令      │
             └──────────┬──────────┘
                        │
             ┌──────────▼──────────┐
             │ Phase 10: trends    │  ← 可并行
             │ 命令 + 配置扩展     │
             └──────────┬──────────┘
                        │
             ┌──────────▼──────────┐
             │ Phase 11: 最终集成  │  ← 全部完成
             │ topic --smart +     │
             │ 跨系统联动          │
             └─────────────────────┘
```

## 新增文件清单

| 文件 | Phase | 行数估算 |
|------|-------|---------|
| `xhs_creator/tracker.py` | 1 | ~200 |
| `xhs_creator/analyzer.py` | 3 | ~150 |
| `xhs_creator/optimizer.py` | 4+5 | ~250 |
| `xhs_creator/commands/rate.py` | 2 | ~50 |
| `xhs_creator/commands/history_cmd.py` | 2 | ~60 |
| `xhs_creator/commands/stats.py` | 3 | ~60 |
| `xhs_creator/commands/prompt_cmd.py` | 4 | ~100 |
| `xhs_creator/recommender/__init__.py` | 7 | ~5 |
| `xhs_creator/recommender/trends.py` | 7 | ~120 |
| `xhs_creator/recommender/profile.py` | 8 | ~120 |
| `xhs_creator/recommender/scorer.py` | 9 | ~100 |
| `xhs_creator/recommender/calendar.py` | 9 | ~60 |
| `xhs_creator/recommender/engine.py` | 9 | ~150 |
| `xhs_creator/commands/recommend.py` | 9 | ~120 |
| `xhs_creator/commands/profile_cmd.py` | 8 | ~60 |
| `xhs_creator/commands/trends_cmd.py` | 10 | ~60 |
| **合计** | | **~1665** |

## 修改文件清单

| 文件 | Phase | 改动 |
|------|-------|------|
| `llm.py` | 1 | +track/command/options 参数, import time |
| `prompts.py` | 4 | +BUILTIN_PROMPTS, +get_prompt(), +RECOMMEND_SYSTEM_PROMPT(11) |
| `config.py` | 10 | +prompt_optimization/recommend 默认配置 |
| `formatter.py` | 2,3,9 | +format_trace_row, +format_stats_report, +format_recommendations |
| `cli.py` | 2,3,4,8,9,10 | +6 个 add_command |
| `commands/topic.py` | 1,11 | +--no-track, +--smart, call_llm 参数 |
| `commands/title.py` | 1,4 | +--no-track, +--prompt-version, get_prompt() |
| `commands/write.py` | 1,4 | +--no-track, +--prompt-version, get_prompt() |
| `commands/analyze.py` | 1 | +--no-track, call_llm 参数 |
| `commands/publish.py` | 6 | +auto mark trace published |
| `__init__.py` | - | 版本号改为 "2.0.0" |
