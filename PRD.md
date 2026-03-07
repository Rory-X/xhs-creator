# PRD: xhs-creator v2.0 新系统设计

> 版本: 1.0 | 日期: 2026-03-07 | 作者: AI Agent

---

## 目录

1. [背景与动机](#1-背景与动机)
2. [系统一：提示词自优化系统](#2-系统一提示词自优化系统)
   - 2.1 概述
   - 2.2 用户故事
   - 2.3 功能需求
   - 2.4 数据模型
   - 2.5 CLI 设计
   - 2.6 模块架构
   - 2.7 实现计划
3. [系统二：智能话题推荐系统](#3-系统二智能话题推荐系统)
   - 3.1 概述
   - 3.2 用户故事
   - 3.3 功能需求
   - 3.4 数据模型
   - 3.5 CLI 设计
   - 3.6 模块架构
   - 3.7 实现计划
4. [跨系统集成](#4-跨系统集成)
5. [技术约束与依赖](#5-技术约束与依赖)

---

## 1. 背景与动机

### 现状分析

xhs-creator v1.1.0 提供了 `topic → title → write → publish` 的完整创作流水线。当前系统存在以下局限：

1. **提示词静态化** — `prompts.py` 中的 4 个 system prompt（TOPIC/TITLE/WRITE/ANALYZE）是硬编码模板，无法根据实际生成效果迭代优化。用户只能通过 `--style`/`--tone` 等参数做粗粒度调整，无法积累"什么 prompt 参数组合产出了高质量内容"的经验。

2. **选题依赖人工** — `topic` 命令需要用户主动输入关键词，或依赖 `domains.primary/secondary` 静态配置。缺少基于历史数据、平台趋势、用户偏好的智能推荐能力。`--hot` 选项虽能联网搜索，但只是把搜索结果原文塞给 LLM，没有结构化的趋势分析和个性化推荐。

### 目标

- **系统一**：建立"生成 → 追踪 → 分析 → 优化"的 prompt 闭环，让 LLM 调用参数随使用逐渐逼近最优。
- **系统二**：建立"数据采集 → 趋势识别 → 个性化推荐"的话题引擎，让用户打开工具就有高质量选题可写。

---

## 2. 系统一：提示词自优化系统

### 2.1 概述

提示词自优化系统由三个核心模块组成：

| 模块 | 职责 | 文件 |
|------|------|------|
| **Tracker** | 记录每次 LLM 调用的输入、参数、输出和用户反馈 | `xhs_creator/tracker.py` |
| **Analyzer** | 分析历史调用数据，识别高效 prompt 模式 | `xhs_creator/analyzer.py` |
| **Optimizer** | 基于分析结论自动调整 prompt 模板和参数 | `xhs_creator/optimizer.py` |

工作流：

```
用户调用命令 (topic/title/write)
       │
       ▼
  Tracker 记录调用上下文
  (prompt, params, response, timestamp)
       │
       ▼
  用户给出反馈 (rating / 是否发布 / 编辑程度)
       │
       ▼
  Tracker 更新反馈字段
       │
       ▼
  Analyzer 定期/手动分析历史数据
  (哪些参数组合评分高？哪些 prompt 片段常被保留？)
       │
       ▼
  Optimizer 生成优化建议 / 自动更新 prompt
```

### 2.2 用户故事

**US-P1: 自动记录创作历史**
> 作为内容创作者，我希望系统自动记录每次内容生成的参数和结果，这样我不需要手动做笔记就能回顾创作历史。

**US-P2: 对生成结果评分**
> 作为创作者，我希望能对生成的内容打分（1-5 星）或标记"采用/废弃"，让系统知道什么样的结果是好的。

**US-P3: 查看创作统计**
> 作为创作者，我希望能查看历史统计（生成次数、平均评分、最常用风格等），了解自己的创作模式。

**US-P4: 分析最优参数**
> 作为创作者，我希望系统能分析出"哪种风格 + 语气 + 篇幅组合评分最高"，帮我找到最佳创作配方。

**US-P5: 自动优化提示词**
> 作为创作者，我希望系统能根据历史数据自动调整 prompt 模板，让每次生成的内容质量持续提升。

**US-P6: 查看优化历史**
> 作为创作者，我希望能查看 prompt 被优化了哪些部分、为什么优化，保持对系统行为的控制感。

**US-P7: 回滚 prompt 变更**
> 作为创作者，如果优化后的 prompt 效果变差，我希望能一键回滚到之前的版本。

### 2.3 功能需求

#### FR-P1: Tracker — 调用追踪

| ID | 需求 | 优先级 |
|----|------|--------|
| FR-P1.1 | 在 `call_llm()` 调用前后自动记录调用上下文（命令类型、prompt 模板、用户输入、参数、LLM 响应、token 用量、耗时） | P0 |
| FR-P1.2 | 每条记录生成唯一 `trace_id`，用于后续反馈关联 | P0 |
| FR-P1.3 | 调用记录持久化存储到 `~/.xhs-creator/traces/` 目录，按月份分文件（`traces-2026-03.jsonl`） | P0 |
| FR-P1.4 | 支持用户对最近一次生成结果评分：`xhs-creator rate <1-5>` | P0 |
| FR-P1.5 | 支持标记采用/废弃：`xhs-creator rate --adopt` / `xhs-creator rate --drop` | P1 |
| FR-P1.6 | 发布成功时自动标记对应 trace 为 `published=true` | P1 |
| FR-P1.7 | 支持查看最近 N 条调用记录：`xhs-creator history [-n 10]` | P1 |
| FR-P1.8 | 当用户编辑 LLM 输出后发布，记录编辑距离（edit_distance）作为隐式反馈 | P2 |

#### FR-P2: Analyzer — 效果分析

| ID | 需求 | 优先级 |
|----|------|--------|
| FR-P2.1 | 按命令类型（topic/title/write）分组统计：调用次数、平均评分、采用率 | P0 |
| FR-P2.2 | 按参数维度交叉分析：style × rating, tone × rating, length × rating | P0 |
| FR-P2.3 | 识别高分组合（Top-K 参数配方）和低分组合 | P0 |
| FR-P2.4 | 分析 prompt 片段与输出质量的相关性（基于用户评分） | P1 |
| FR-P2.5 | 生成文本分析报告输出到终端 | P0 |
| FR-P2.6 | 支持指定时间范围分析：`--since 2026-01-01` / `--last 30d` | P1 |
| FR-P2.7 | 对比不同时期的生成质量趋势（优化前 vs 优化后） | P2 |

#### FR-P3: Optimizer — Prompt 优化

| ID | 需求 | 优先级 |
|----|------|--------|
| FR-P3.1 | 基于 Analyzer 结论，调用 LLM 生成 prompt 优化建议 | P0 |
| FR-P3.2 | 优化建议包含：修改点、修改理由、预期效果 | P0 |
| FR-P3.3 | 支持两种模式：`suggest`（仅建议）和 `apply`（自动应用） | P0 |
| FR-P3.4 | prompt 变更以版本化方式存储到 `~/.xhs-creator/prompt_versions/` | P0 |
| FR-P3.5 | 每个版本记录：版本号、变更内容 diff、变更理由、生效时间 | P0 |
| FR-P3.6 | 支持回滚到指定版本：`xhs-creator prompt rollback [version]` | P0 |
| FR-P3.7 | 支持查看当前生效的 prompt 模板：`xhs-creator prompt show <type>` | P1 |
| FR-P3.8 | 优化时自动将高分 trace 的输出作为 few-shot 示例注入 prompt | P2 |
| FR-P3.9 | 设置自动优化阈值：累积 N 条新评分后自动触发分析和优化 | P2 |

### 2.4 数据模型

#### Trace 记录（JSONL 格式）

```json
{
  "trace_id": "tr_20260307_143022_a1b2c3",
  "timestamp": "2026-03-07T14:30:22+08:00",
  "command": "write",
  "input": {
    "query": "AI编程入门教程",
    "options": {
      "style": "干货",
      "tone": "专业",
      "length": "medium",
      "tags": null
    }
  },
  "prompt": {
    "template_name": "WRITE_SYSTEM_PROMPT",
    "template_version": "v3",
    "rendered": "你是小红书内容创作专家..."
  },
  "response": {
    "content": "...(LLM 原始输出)",
    "parsed": { "...": "...(解析后的 JSON)" },
    "model": "grok-4.20-beta",
    "tokens": { "prompt": 520, "completion": 890 },
    "latency_ms": 12340
  },
  "feedback": {
    "rating": null,
    "adopted": null,
    "published": false,
    "edit_distance": null,
    "feedback_time": null
  }
}
```

#### Prompt 版本记录

```json
{
  "version": "v3",
  "template_name": "WRITE_SYSTEM_PROMPT",
  "created_at": "2026-03-07T15:00:00+08:00",
  "parent_version": "v2",
  "content": "你是小红书内容创作专家...(完整 prompt 文本)",
  "change_summary": "增加了对小标题格式的约束，基于分析发现带小标题的内容评分高 0.8 分",
  "change_reason": "analyzer_auto",
  "metrics_at_creation": {
    "avg_rating": 3.8,
    "sample_size": 42,
    "top_style": "干货"
  }
}
```

#### 分析报告

```json
{
  "report_id": "rpt_20260307",
  "generated_at": "2026-03-07T16:00:00+08:00",
  "period": { "from": "2026-02-01", "to": "2026-03-07" },
  "summary": {
    "total_traces": 156,
    "rated_traces": 89,
    "avg_rating": 3.6,
    "adopt_rate": 0.72,
    "publish_rate": 0.45
  },
  "by_command": {
    "write": { "count": 68, "avg_rating": 3.8, "adopt_rate": 0.75 },
    "title": { "count": 52, "avg_rating": 3.5, "adopt_rate": 0.70 },
    "topic": { "count": 36, "avg_rating": 3.4, "adopt_rate": 0.68 }
  },
  "top_combinations": [
    { "style": "干货", "tone": "专业", "length": "medium", "avg_rating": 4.3, "count": 12 },
    { "style": "种草", "tone": "活泼", "length": "short", "avg_rating": 4.1, "count": 8 }
  ],
  "worst_combinations": [
    { "style": "测评", "tone": "搞笑", "length": "long", "avg_rating": 2.1, "count": 5 }
  ],
  "optimization_suggestions": [
    "write 命令的默认风格建议从「种草」改为「干货」（评分差 +0.5）",
    "title 命令中「悬念」风格标题采用率最高（78%），建议增加悬念类 prompt 权重"
  ]
}
```

### 2.5 CLI 设计

#### 新增命令

```bash
# ── 评分反馈 ──
xhs-creator rate 4                    # 对最近一次生成打分 (1-5)
xhs-creator rate 5 --adopt            # 打分 + 标记采用
xhs-creator rate --drop               # 标记废弃（不打分）
xhs-creator rate 3 --trace <trace_id> # 对指定 trace 打分

# ── 历史查看 ──
xhs-creator history                   # 最近 10 条调用记录
xhs-creator history -n 20             # 最近 20 条
xhs-creator history --command write   # 只看 write 命令的记录
xhs-creator history --rated           # 只看已评分的记录
xhs-creator history --json            # JSON 输出

# ── 效果分析 ──
xhs-creator stats                     # 全量统计概览
xhs-creator stats --command write     # write 命令的详细分析
xhs-creator stats --since 2026-02-01  # 指定时间范围
xhs-creator stats --last 30d          # 最近 30 天
xhs-creator stats --json              # JSON 输出

# ── Prompt 管理 ──
xhs-creator prompt show write         # 查看 write 命令当前的 prompt
xhs-creator prompt show title         # 查看 title 命令当前的 prompt
xhs-creator prompt versions write     # 查看 write prompt 的版本历史
xhs-creator prompt optimize           # 分析数据并生成优化建议（所有命令）
xhs-creator prompt optimize write     # 只优化 write 命令的 prompt
xhs-creator prompt apply write        # 应用最新优化建议
xhs-creator prompt rollback write     # 回滚到上一版本
xhs-creator prompt rollback write v2  # 回滚到指定版本
xhs-creator prompt reset write        # 恢复为内置默认 prompt
```

#### 现有命令增强

```bash
# topic/title/write 命令新增选项
xhs-creator write -t "AI编程" --no-track   # 本次不记录 trace
xhs-creator write -t "AI编程" --prompt-version v2  # 使用指定版本 prompt

# publish 命令自动关联 trace
xhs-creator publish -t "标题" -c "内容"
# → 自动将最近一次 write trace 标记为 published=true
```

### 2.6 模块架构

```
xhs_creator/
├── tracker.py              # Tracker 模块
│   ├── generate_trace_id()
│   ├── start_trace(command, input, prompt_info) → trace_id
│   ├── end_trace(trace_id, response)
│   ├── add_feedback(trace_id, rating, adopted, published)
│   ├── get_recent_traces(n, command, rated_only) → List[Trace]
│   ├── get_last_trace_id() → str
│   └── load_traces(since, until, command) → List[Trace]
│
├── analyzer.py             # Analyzer 模块
│   ├── compute_stats(traces) → AnalysisReport
│   ├── find_top_combinations(traces, top_k) → List[Combination]
│   ├── find_worst_combinations(traces, min_count) → List[Combination]
│   ├── compare_prompt_versions(template_name) → VersionComparison
│   └── generate_report(since, until, command) → AnalysisReport
│
├── optimizer.py            # Optimizer 模块
│   ├── suggest_optimization(template_name, report) → List[Suggestion]
│   ├── apply_optimization(template_name, suggestion) → new_version
│   ├── get_current_prompt(template_name) → PromptVersion
│   ├── list_versions(template_name) → List[PromptVersion]
│   ├── rollback(template_name, target_version)
│   └── reset_to_default(template_name)
│
├── commands/
│   ├── rate.py             # rate 命令
│   ├── history_cmd.py      # history 命令
│   ├── stats.py            # stats 命令
│   └── prompt_cmd.py       # prompt 命令组
│
├── llm.py                  # 修改: call_llm() 集成 tracker
├── prompts.py              # 修改: 支持从版本化存储加载 prompt
└── cli.py                  # 修改: 注册新命令
```

#### Tracker 与 call_llm 集成方式

```python
# llm.py 中的集成（伪代码）
def call_llm(query, system_prompt, model=None, track=True, command=None, options=None):
    trace_id = None
    if track:
        trace_id = tracker.start_trace(command, {"query": query, "options": options}, ...)

    # ... 原有调用逻辑 ...

    if track and trace_id:
        tracker.end_trace(trace_id, {"content": ..., "model": ..., "tokens": ...})

    result["_trace_id"] = trace_id  # 附带 trace_id 供后续反馈
    return result
```

#### prompts.py 版本化加载

```python
# prompts.py 中的增强（伪代码）
def get_prompt(template_name, version=None, **kwargs):
    """加载 prompt 模板，优先使用版本化存储，fallback 到内置默认"""
    if version:
        content = optimizer.get_prompt_by_version(template_name, version)
    else:
        content = optimizer.get_current_prompt(template_name)

    if content is None:
        # fallback 到内置模板
        content = BUILTIN_PROMPTS[template_name]

    return content.format(**kwargs)
```

### 2.7 实现计划

| 阶段 | 内容 | 涉及文件 | 依赖 |
|------|------|----------|------|
| **Phase 1: Tracker 基础** | trace 数据模型、JSONL 读写、`start_trace`/`end_trace`、`call_llm` 集成 | `tracker.py`, `llm.py` | 无 |
| **Phase 2: 反馈收集** | `rate` 命令、`history` 命令、`get_last_trace_id` | `commands/rate.py`, `commands/history_cmd.py`, `cli.py` | Phase 1 |
| **Phase 3: 统计分析** | `compute_stats`、`find_top_combinations`、`stats` 命令 | `analyzer.py`, `commands/stats.py`, `formatter.py` | Phase 1 |
| **Phase 4: Prompt 版本管理** | 版本化存储、`show`/`versions`/`rollback`/`reset` 命令 | `optimizer.py`, `commands/prompt_cmd.py`, `prompts.py` | 无 |
| **Phase 5: 自动优化** | `suggest_optimization`（调用 LLM 分析）、`apply` 命令、few-shot 注入 | `optimizer.py` | Phase 3 + Phase 4 |
| **Phase 6: 闭环集成** | publish 自动标记、edit_distance 计算、自动触发优化 | `commands/publish.py`, `tracker.py`, `optimizer.py` | Phase 2 + Phase 5 |

---

## 3. 系统二：智能话题推荐系统

### 3.1 概述

智能话题推荐系统（Recommender）构建在现有 `topic` 命令和 `xhs_client` 之上，提供基于多维度信号的个性化话题推荐：

| 信号源 | 描述 |
|--------|------|
| **平台趋势** | 通过 MCP 搜索小红书热门笔记，提取当前热点话题 |
| **用户偏好** | 基于 `domains` 配置 + Tracker 历史数据中的高分领域 |
| **时间因素** | 节假日、季节、社会热点等时间相关因素 |
| **内容缺口** | 用户已创作过的话题 vs 尚未覆盖的领域 |
| **竞品分析** | 同领域高互动笔记的选题模式 |

核心模块：

| 模块 | 职责 | 文件 |
|------|------|------|
| **TrendCollector** | 从小红书采集热门话题数据并缓存 | `xhs_creator/recommender/trends.py` |
| **UserProfile** | 构建和维护用户兴趣画像 | `xhs_creator/recommender/profile.py` |
| **TopicScorer** | 多维度话题评分与排序 | `xhs_creator/recommender/scorer.py` |
| **Recommender** | 组合上述模块，输出最终推荐列表 | `xhs_creator/recommender/engine.py` |

工作流：

```
                  ┌─────────────┐
                  │ TrendCollector│
                  │ (小红书热门)  │
                  └──────┬──────┘
                         │
    ┌──────────┐    ┌────▼────┐    ┌──────────┐
    │UserProfile│───▶│  Scorer │◀───│ Calendar │
    │(用户画像) │    │(多维评分)│    │(时间因素) │
    └──────────┘    └────┬────┘    └──────────┘
                         │
                  ┌──────▼──────┐
                  │ Recommender │
                  │ (推荐引擎)   │
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │  推荐结果    │
                  │ (排序+理由)  │
                  └─────────────┘
```

### 3.2 用户故事

**US-R1: 每日话题推荐**
> 作为创作者，我希望每天打开工具就能看到为我量身定制的选题建议，不再为"今天写什么"发愁。

**US-R2: 基于热点的推荐**
> 作为创作者，我希望系统能发现与我擅长领域相关的实时热点，帮我蹭上热度。

**US-R3: 避免重复选题**
> 作为创作者，我希望系统推荐的话题不会和我已经写过的内容重复，保持新鲜感。

**US-R4: 推荐理由透明**
> 作为创作者，我希望每个推荐话题都附带推荐理由（为什么推荐、预估热度），帮我做决策。

**US-R5: 一键从推荐到创作**
> 作为创作者，我希望看到好的推荐后能一键进入标题生成和正文写作流程，减少操作步骤。

**US-R6: 调整推荐偏好**
> 作为创作者，我希望能对推荐结果"点赞/踩"来调整后续推荐方向。

**US-R7: 定时推送推荐**
> 作为创作者，我希望系统能在我设定的时间（如每天早上 9 点）自动生成推荐并保存，随时查看。

**US-R8: 跨领域探索**
> 作为创作者，我希望偶尔收到领域外但与我技能相关的"跨界"推荐，发掘新的创作方向。

### 3.3 功能需求

#### FR-R1: TrendCollector — 趋势采集

| ID | 需求 | 优先级 |
|----|------|--------|
| FR-R1.1 | 基于用户配置的 `domains`，定期通过 MCP `search_notes` 采集各领域热门笔记 | P0 |
| FR-R1.2 | 从搜索结果中提取结构化趋势数据：热门标签、高频关键词、互动量分布 | P0 |
| FR-R1.3 | 趋势数据缓存到 `~/.xhs-creator/trends/`，带 TTL（默认 6 小时） | P0 |
| FR-R1.4 | 缓存未过期时直接使用，避免重复调用 MCP | P0 |
| FR-R1.5 | 支持手动刷新：`xhs-creator recommend --refresh` | P1 |
| FR-R1.6 | 支持配置自动采集的关键词列表和采集频率 | P2 |

#### FR-R2: UserProfile — 用户画像

| ID | 需求 | 优先级 |
|----|------|--------|
| FR-R2.1 | 从 `config.yaml` 的 `domains` 配置构建基础兴趣画像 | P0 |
| FR-R2.2 | 从 Tracker 历史数据中提取：常用风格、高分领域、创作频率 | P0 |
| FR-R2.3 | 维护已创作话题列表（从 trace 中提取），用于去重 | P0 |
| FR-R2.4 | 根据推荐反馈（点赞/踩）动态调整兴趣权重 | P1 |
| FR-R2.5 | 用户画像持久化到 `~/.xhs-creator/profile.yaml` | P0 |
| FR-R2.6 | 支持查看和手动编辑画像：`xhs-creator profile show` / `xhs-creator profile edit` | P1 |

#### FR-R3: TopicScorer — 话题评分

| ID | 需求 | 优先级 |
|----|------|--------|
| FR-R3.1 | 综合以下维度计算话题得分：趋势热度(0-1)、用户匹配度(0-1)、新鲜度(0-1)、时效性(0-1) | P0 |
| FR-R3.2 | 各维度权重可配置（`config.yaml` 中的 `recommend.weights`） | P1 |
| FR-R3.3 | 新鲜度：与用户已创作话题的语义相似度取反，越不同分越高 | P0 |
| FR-R3.4 | 时效性：结合当前日期、节假日、季节因素加分（如春节前"年货"话题加分） | P1 |
| FR-R3.5 | 支持"探索模式"：随机提升低匹配度话题的权重，鼓励跨领域尝试 | P2 |

#### FR-R4: Recommender — 推荐引擎

| ID | 需求 | 优先级 |
|----|------|--------|
| FR-R4.1 | 调用 LLM 基于趋势数据 + 用户画像生成 N 个推荐话题 | P0 |
| FR-R4.2 | 每个推荐包含：话题标题、推荐理由、预估热度(1-5)、建议风格、关联标签 | P0 |
| FR-R4.3 | 使用 TopicScorer 对 LLM 生成的话题重排序 | P0 |
| FR-R4.4 | 去重：过滤掉与用户近期创作话题高度相似的推荐 | P0 |
| FR-R4.5 | 推荐结果缓存，同一天内多次调用不重复生成（除非 `--refresh`） | P1 |
| FR-R4.6 | 支持按领域过滤推荐：`xhs-creator recommend --domain "AI"` | P1 |
| FR-R4.7 | 推荐结果可直接传递给 `title`/`write` 命令继续创作 | P0 |

### 3.4 数据模型

#### 趋势缓存（trends-{domain}-{date}.json）

```json
{
  "domain": "AI",
  "collected_at": "2026-03-07T09:00:00+08:00",
  "ttl_hours": 6,
  "hot_topics": [
    {
      "keyword": "AI编程",
      "mention_count": 45,
      "avg_likes": 1230,
      "avg_collects": 456,
      "trend": "rising",
      "sample_titles": ["3天学会AI编程", "AI写代码替代程序员？"]
    }
  ],
  "hot_tags": ["AI编程", "ChatGPT", "提效工具"],
  "hot_keywords": ["Claude", "Cursor", "AI编程", "提示词"]
}
```

#### 用户画像（profile.yaml）

```yaml
# 自动生成 + 可手动编辑
interests:
  primary: "AI技术"
  domains:
    AI技术: { weight: 0.9, source: "config+history" }
    编程教程: { weight: 0.7, source: "history" }
    科技数码: { weight: 0.5, source: "config" }

style_preference:
  preferred: ["干货", "教程"]
  avoid: ["搞笑"]

created_topics:
  - { topic: "AI编程入门", date: "2026-03-01", rating: 4 }
  - { topic: "Claude使用技巧", date: "2026-03-05", rating: 5 }

feedback_history:
  liked_recommendations: ["AI绘画教程", "Cursor插件推荐"]
  disliked_recommendations: ["AI取代人类讨论"]

updated_at: "2026-03-07T10:00:00+08:00"
```

#### 推荐结果（recommendations-{date}.json）

```json
{
  "generated_at": "2026-03-07T09:30:00+08:00",
  "profile_version": "2026-03-07",
  "recommendations": [
    {
      "id": "rec_001",
      "topic": "Claude 4.5 实测：10 个让效率翻倍的 prompt 技巧",
      "reason": "AI技术领域热度上升中，结合你擅长的教程风格，且近期未创作过 prompt 相关内容",
      "heat_score": 5,
      "freshness_score": 0.92,
      "match_score": 0.88,
      "final_score": 0.90,
      "suggested_style": "干货",
      "suggested_tone": "专业",
      "tags": ["AI工具", "Claude", "提效"],
      "source": "trend+profile",
      "feedback": null
    }
  ]
}
```

#### 日历事件数据（内置）

```json
{
  "calendar_events": [
    { "date_pattern": "MM-14", "month": 2, "name": "情人节", "boost_tags": ["情人节", "礼物", "约会"] },
    { "date_pattern": "MM-08", "month": 3, "name": "妇女节", "boost_tags": ["女性", "独立", "自我提升"] },
    { "season": "spring", "name": "春季", "boost_tags": ["春游", "换季", "新开始"] }
  ]
}
```

### 3.5 CLI 设计

#### 新增命令

```bash
# ── 话题推荐 ──
xhs-creator recommend                    # 获取今日推荐（默认 5 个）
xhs-creator recommend -n 10              # 推荐 10 个话题
xhs-creator recommend --domain "AI"      # 限定领域
xhs-creator recommend --explore          # 探索模式（含跨领域推荐）
xhs-creator recommend --refresh          # 强制刷新（忽略缓存）
xhs-creator recommend --json             # JSON 输出

# ── 推荐交互 ──
xhs-creator recommend pick 1             # 选择第 1 个推荐，进入创作流程
xhs-creator recommend pick 3 --title     # 选择第 3 个，直接生成标题
xhs-creator recommend pick 2 --write     # 选择第 2 个，直接生成正文
xhs-creator recommend like 1             # 对第 1 个推荐点赞
xhs-creator recommend dislike 3          # 对第 3 个推荐踩

# ── 用户画像 ──
xhs-creator profile show                 # 查看当前画像
xhs-creator profile show --json          # JSON 输出
xhs-creator profile refresh              # 基于最新历史数据重建画像
xhs-creator profile add-domain "美食"    # 手动添加感兴趣领域
xhs-creator profile remove-domain "美食" # 移除领域

# ── 趋势查看 ──
xhs-creator trends                       # 查看各领域当前趋势
xhs-creator trends "AI"                  # 查看 AI 领域趋势详情
xhs-creator trends --refresh             # 强制刷新趋势数据
```

#### 现有命令增强

```bash
# topic 命令集成推荐
xhs-creator topic                        # 无参数时自动使用推荐引擎（当前行为: 用 domains 配置）
xhs-creator topic --smart                # 显式启用智能推荐模式
```

### 3.6 模块架构

```
xhs_creator/
├── recommender/
│   ├── __init__.py           # 包入口，导出 Recommender
│   ├── trends.py             # TrendCollector
│   │   ├── collect_trends(domains) → Dict[str, TrendData]
│   │   ├── get_cached_trends(domain) → TrendData | None
│   │   ├── is_cache_valid(domain) → bool
│   │   └── refresh_trends(domain)
│   │
│   ├── profile.py            # UserProfile
│   │   ├── build_profile(config, traces) → Profile
│   │   ├── load_profile() → Profile
│   │   ├── save_profile(profile)
│   │   ├── update_from_feedback(rec_id, liked: bool)
│   │   ├── add_domain(domain)
│   │   ├── remove_domain(domain)
│   │   └── get_created_topics() → List[str]
│   │
│   ├── scorer.py             # TopicScorer
│   │   ├── score_topic(topic, profile, trends, calendar) → ScoredTopic
│   │   ├── compute_trend_score(topic, trends) → float
│   │   ├── compute_match_score(topic, profile) → float
│   │   ├── compute_freshness(topic, created_topics) → float
│   │   ├── compute_timeliness(topic, calendar) → float
│   │   └── rank_topics(topics) → List[ScoredTopic]
│   │
│   ├── calendar.py           # 时间因素（节假日、季节）
│   │   ├── get_current_events() → List[CalendarEvent]
│   │   └── get_boost_tags() → List[str]
│   │
│   └── engine.py             # Recommender 主引擎
│       ├── generate_recommendations(n, domain, explore) → List[Recommendation]
│       ├── get_cached_recommendations() → List[Recommendation] | None
│       ├── pick_recommendation(index) → Recommendation
│       └── feedback(rec_id, liked: bool)
│
├── commands/
│   ├── recommend.py          # recommend 命令组
│   ├── profile_cmd.py        # profile 命令组
│   └── trends_cmd.py         # trends 命令
│
└── cli.py                    # 修改: 注册新命令
```

#### Recommender 核心逻辑

```python
# engine.py 伪代码
class Recommender:
    def generate_recommendations(self, n=5, domain=None, explore=False):
        # 1. 加载用户画像
        profile = UserProfile.load_profile()

        # 2. 采集趋势（带缓存）
        domains = [domain] if domain else profile.get_domains()
        trends = TrendCollector.collect_trends(domains)

        # 3. 获取时间因素
        calendar_events = Calendar.get_current_events()
        boost_tags = Calendar.get_boost_tags()

        # 4. 构造 LLM prompt，生成候选话题
        context = self._build_context(profile, trends, calendar_events, boost_tags)
        candidates = self._llm_generate_topics(context, n=n*2)  # 多生成一些用于筛选

        # 5. 评分排序
        scored = [TopicScorer.score_topic(t, profile, trends, calendar_events) for t in candidates]
        scored.sort(key=lambda x: x.final_score, reverse=True)

        # 6. 去重过滤
        created = profile.get_created_topics()
        filtered = [t for t in scored if self._is_novel(t, created)]

        # 7. 探索模式：插入 1-2 个低匹配但高热度的跨领域话题
        if explore:
            filtered = self._inject_exploration(filtered, trends, profile)

        return filtered[:n]
```

### 3.7 实现计划

| 阶段 | 内容 | 涉及文件 | 依赖 |
|------|------|----------|------|
| **Phase 1: TrendCollector** | MCP 热门数据采集、结构化提取、缓存机制 | `recommender/trends.py`, `xhs_client.py` | MCP 服务 |
| **Phase 2: UserProfile 基础** | 从 config 构建画像、画像持久化、`profile` 命令 | `recommender/profile.py`, `commands/profile_cmd.py` | 无 |
| **Phase 3: 推荐引擎 MVP** | LLM 生成候选话题、基础评分（热度+匹配度）、`recommend` 命令基础功能 | `recommender/engine.py`, `recommender/scorer.py`, `commands/recommend.py` | Phase 1 + Phase 2 |
| **Phase 4: 日历与时效性** | 内置日历数据、时效性评分维度 | `recommender/calendar.py`, `recommender/scorer.py` | Phase 3 |
| **Phase 5: 去重与新鲜度** | 已创作话题提取、语义相似度、新鲜度评分 | `recommender/profile.py`, `recommender/scorer.py` | Phase 3 + 系统一 Tracker |
| **Phase 6: 推荐反馈闭环** | `like`/`dislike`、画像动态更新、推荐交互流（`pick`） | `recommender/engine.py`, `recommender/profile.py` | Phase 3 |
| **Phase 7: 探索模式** | 跨领域推荐注入、`--explore` 选项 | `recommender/engine.py`, `recommender/scorer.py` | Phase 3 |
| **Phase 8: trends 命令** | 独立趋势查看命令 | `commands/trends_cmd.py` | Phase 1 |

---

## 4. 跨系统集成

两个系统在以下关键点产生协同：

### 4.1 Tracker 为 Recommender 提供数据

```
Tracker.load_traces()
    │
    ├── UserProfile.build_profile()  ← 提取用户偏好和创作历史
    │
    └── Scorer.compute_freshness()   ← 已创作话题用于去重
```

- Recommender 的 `UserProfile` 依赖 Tracker 的历史 trace 数据来理解用户的创作偏好（高分风格、常用领域等）
- Scorer 的新鲜度计算依赖 Tracker 中记录的已创作话题列表

### 4.2 Recommender 反馈流入 Tracker

```
recommend pick 3 --write
    │
    ├── 记录推荐来源到 trace: source="recommendation:rec_001"
    │
    └── 后续 rate 评分同时反馈给:
        ├── Tracker (prompt 优化)
        └── Recommender (推荐优化)
```

- 用户通过 `recommend pick` 进入创作流程时，生成的 trace 中记录推荐来源
- 对该 trace 的评分同时用于 prompt 优化和推荐算法调优

### 4.3 Optimizer 影响 Recommender 的 LLM 调用

```
Optimizer.get_current_prompt("RECOMMEND_SYSTEM_PROMPT")
    │
    └── Recommender._llm_generate_topics() 使用优化后的 prompt
```

- Recommender 的 LLM 调用也纳入 Tracker 追踪和 Optimizer 优化范围
- 新增 `RECOMMEND_SYSTEM_PROMPT` 模板，同样支持版本化管理

### 4.4 统一配置扩展

```yaml
# config.yaml 新增配置项

# 提示词自优化
prompt_optimization:
  auto_optimize: false           # 是否自动优化（达到阈值后）
  auto_optimize_threshold: 20    # 累积多少条评分后自动触发
  optimization_model: null       # 用于优化的模型（null = 使用默认模型）

# 智能推荐
recommend:
  enabled: true
  daily_count: 5                 # 每日推荐数量
  cache_ttl_hours: 6             # 趋势缓存有效期
  weights:                       # 评分维度权重
    trend: 0.3
    match: 0.3
    freshness: 0.25
    timeliness: 0.15
  explore_ratio: 0.2             # 探索模式下跨领域推荐占比
  auto_collect_domains: []       # 额外自动采集趋势的领域
```

---

## 5. 技术约束与依赖

### 5.1 技术约束

| 约束 | 说明 |
|------|------|
| Python 3.8+ 兼容 | 不使用 3.9+ 专属语法（如 `dict \| None`），保持与现有代码一致 |
| 无新外部依赖 | 仅使用标准库 + 现有依赖（click, pyyaml, pillow）。语义相似度用简单关键词重叠而非 embedding |
| JSONL 存储 | 不引入数据库，使用 JSONL 文件存储 trace 数据，按月分文件控制体积 |
| LLM 调用复用 | 通过现有 `call_llm()` 函数调用 LLM，不新增 API 客户端 |
| MCP 服务依赖 | 趋势采集依赖 MCP 服务运行，推荐功能在 MCP 不可用时降级为纯 LLM 生成 |
| 离线可用 | Tracker 和 Analyzer 完全离线可用，Recommender 在无网络时使用缓存数据 |

### 5.2 存储目录规划

```
~/.xhs-creator/
├── config.yaml                      # 现有配置（扩展）
├── history/                         # 现有历史目录
├── traces/                          # [新] Tracker 数据
│   ├── traces-2026-03.jsonl
│   └── traces-2026-02.jsonl
├── prompt_versions/                 # [新] Prompt 版本
│   ├── WRITE_SYSTEM_PROMPT/
│   │   ├── v1.json
│   │   ├── v2.json
│   │   └── current -> v2.json
│   ├── TITLE_SYSTEM_PROMPT/
│   └── TOPIC_SYSTEM_PROMPT/
├── profile.yaml                     # [新] 用户画像
├── trends/                          # [新] 趋势缓存
│   ├── trends-AI-2026-03-07.json
│   └── trends-编程-2026-03-07.json
└── recommendations/                 # [新] 推荐缓存
    └── recommendations-2026-03-07.json
```

### 5.3 整体实施优先级

```
Phase 1-2 (系统一 Tracker + 反馈)     ← 基础设施，两个系统都依赖
    │
    ├── Phase 3 (系统一 Analyzer)
    │       │
    │       └── Phase 5 (系统一 Optimizer)
    │               │
    │               └── Phase 6 (系统一 闭环)
    │
    └── Phase 1-2 (系统二 TrendCollector + UserProfile)
            │
            ├── Phase 3 (系统二 推荐 MVP)
            │       │
            │       ├── Phase 4 (系统二 日历)
            │       ├── Phase 5 (系统二 去重)
            │       ├── Phase 6 (系统二 反馈闭环)
            │       └── Phase 7 (系统二 探索模式)
            │
            └── Phase 8 (系统二 trends 命令)
```

建议先完成系统一的 Phase 1-3（Tracker + 反馈 + 统计），因为这是两个系统共享的基础设施。之后两个系统可以并行推进。
