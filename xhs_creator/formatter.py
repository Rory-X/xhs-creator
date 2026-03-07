"""输出格式化模块 - 支持 text 和 json 双模式输出"""

import json
import re

import click


def output_json(data):
    """JSON 格式输出"""
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def format_parse_failure(raw_content):
    """JSON 解析失败时的友好降级输出

    清理 think 标签和 markdown 代码块后显示原文。
    """
    click.echo(click.style("⚠ 内容生成成功但格式解析失败，原文如下：\n", fg="yellow"))
    # 清理常见的包裹标记
    text = raw_content
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    click.echo(text)
    click.echo()


def format_topics(data, keyword):
    """格式化选题列表（文本模式）"""
    topics = data.get("topics", [])
    count = len(topics)

    click.echo(click.style(f'\n🔥 "{keyword}" 选题建议 ({count}条)\n', fg="yellow", bold=True))

    for i, topic in enumerate(topics, 1):
        title = topic.get("title", "")
        angle = topic.get("angle", "")
        heat = topic.get("heat_score", 0)
        tags = topic.get("tags", [])

        heat_stars = "⭐" * min(heat, 5)

        click.echo(click.style(f"  {i}. 【{title}】", fg="bright_white", bold=True))
        click.echo(f"     角度: {angle}")
        click.echo(f"     预估热度: {heat_stars}")
        if tags:
            click.echo(f"     标签: {' '.join('#' + t for t in tags)}")
        click.echo()


def format_titles(data, original):
    """格式化标题列表（文本模式）"""
    titles = data.get("titles", [])

    click.echo(click.style(f'\n✨ 标题优化建议 (基于: "{original}")\n', fg="cyan", bold=True))

    for i, title in enumerate(titles, 1):
        text = title.get("text", "")
        char_count = title.get("char_count", len(text))
        style = title.get("style", "")

        click.echo(click.style(f"  {i}. {text}", fg="bright_white"))
        click.echo(click.style(f"     [{style}] {char_count}字", fg="bright_black"))
        click.echo()


def format_article(data):
    """格式化正文（文本模式）"""
    content = data.get("content", "")
    char_count = data.get("char_count", len(content))
    tags = data.get("tags", [])
    image_tips = data.get("image_tips", {})

    click.echo(click.style("\n📝 正文生成完成\n", fg="green", bold=True))
    click.echo(click.style("--- 正文 ---", fg="bright_black"))
    click.echo(content)
    click.echo()

    if tags:
        click.echo(" ".join(f"#{t}" for t in tags))
        click.echo()

    click.echo(click.style(f"字数: {char_count}", fg="bright_black"))

    if image_tips and (image_tips.get("cover") or image_tips.get("images")):
        click.echo(click.style("\n--- 图片建议 ---", fg="bright_black"))
        cover = image_tips.get("cover", "")
        if cover:
            click.echo(f"  封面: {cover}")
        images = image_tips.get("images", [])
        for i, img in enumerate(images, 1):
            click.echo(f"  图{i}: {img}")

    click.echo()


def format_analysis(data):
    """格式化分析报告（文本模式）"""
    keyword = data.get("keyword", "")
    count = data.get("analyzed_count", 0)
    summary = data.get("summary", {})
    suggestions = data.get("suggestions", [])

    click.echo(click.style(
        f'\n🔍 竞品分析: "{keyword}" (共分析 {count} 篇笔记)\n',
        fg="magenta", bold=True,
    ))

    click.echo(click.style("📊 爆款特征总结:", fg="yellow", bold=True))
    click.echo(f"  标题规律: {summary.get('title_pattern', '-')}")
    click.echo(f"  平均标题字数: {summary.get('avg_title_length', '-')}")
    click.echo(f"  内容结构: {summary.get('content_structure', '-')}")

    top_tags = summary.get("top_tags", [])
    if top_tags:
        click.echo(f"  常用标签: {' '.join('#' + t for t in top_tags)}")

    top_kw = summary.get("top_keywords", [])
    if top_kw:
        click.echo(f"  高频词汇: {'、'.join(top_kw)}")

    click.echo(
        f"  互动数据: 平均点赞 {summary.get('avg_likes', '-')}, "
        f"收藏 {summary.get('avg_collects', '-')}, "
        f"评论 {summary.get('avg_comments', '-')}"
    )

    if suggestions:
        click.echo(click.style("\n💡 创作建议:", fg="green", bold=True))
        for i, s in enumerate(suggestions, 1):
            click.echo(f"  {i}. {s}")

    click.echo()


def format_publish_preview(title, content, images=None):
    """格式化发布预览"""
    click.echo(click.style("\n📤 发布预览:", fg="cyan", bold=True))
    click.echo(f"  标题: {title}")

    content_preview = content[:50] + "..." if len(content) > 50 else content
    click.echo(f"  正文: ({len(content)}字) {content_preview}")

    if images:
        click.echo(f"  图片: {len(images)}张 ({', '.join(images)})")

    click.echo()


def format_trace_row(trace):
    """格式化单条 trace 为终端行"""
    trace_id = trace.get("trace_id", "")
    # 截短显示（后8位）
    short_id = trace_id[-8:] if len(trace_id) > 8 else trace_id

    command = trace.get("command", "?")
    query = trace.get("input", {}).get("query", "").replace("\n", " ").strip()
    if len(query) > 30:
        query = query[:30] + "..."

    fb = trace.get("feedback", {})
    rating = fb.get("rating")
    rating_str = "⭐" * rating if rating else "-"

    adopted = fb.get("adopted")
    if adopted is True:
        status = click.style("✓", fg="green")
    elif adopted is False:
        status = click.style("✗", fg="red")
    else:
        status = "-"

    ts = trace.get("timestamp", "")[:16]  # YYYY-MM-DDTHH:MM

    # 命令用颜色标签
    cmd_colors = {"topic": "yellow", "title": "cyan", "write": "green", "analyze": "magenta"}
    cmd_color = cmd_colors.get(command, "white")
    cmd_str = click.style(command, fg=cmd_color)

    click.echo(f"  {click.style(short_id, fg='bright_black')} | {cmd_str} | {query} | {rating_str} | {status} | {click.style(ts, fg='bright_black')}")


def format_history_table(traces):
    """格式化 trace 列表为表格"""
    click.echo(click.style("\n📋 调用历史\n", fg="cyan", bold=True))
    click.echo(click.style(
        f"  {'ID':>8} | {'命令':6} | {'查询':30} | {'评分':5} | {'状态':3} | 时间",
        fg="bright_black",
    ))
    click.echo(click.style("  " + "-" * 78, fg="bright_black"))

    for t in traces:
        format_trace_row(t)

    click.echo()


def format_stats_report(report):
    """格式化统计报告"""
    summary = report.get("summary", {})

    click.echo(click.style("\n📊 创作统计报告\n", fg="cyan", bold=True))

    # 总览
    click.echo(click.style("总览:", fg="yellow", bold=True))
    click.echo(f"  总调用次数: {summary.get('total_traces', 0)}")
    click.echo(f"  已评分次数: {summary.get('rated_traces', 0)}")

    avg = summary.get("avg_rating", 0)
    if avg > 0:
        click.echo(f"  平均评分: {avg} {'⭐' * round(avg)}")
    else:
        click.echo("  平均评分: -")

    adopt = summary.get("adopt_rate", 0)
    click.echo(f"  采用率: {int(adopt * 100)}%")
    publish = summary.get("publish_rate", 0)
    click.echo(f"  发布率: {int(publish * 100)}%")

    # 按命令分组
    by_cmd = summary.get("by_command", {})
    if by_cmd:
        click.echo(click.style("\n按命令统计:", fg="yellow", bold=True))
        for cmd, data in sorted(by_cmd.items()):
            r = data.get("avg_rating", 0)
            rating_str = f"{r} {'⭐' * round(r)}" if r > 0 else "-"
            click.echo(f"  {cmd:10} {data.get('count', 0)} 次 | 评分 {rating_str} | 采用率 {int(data.get('adopt_rate', 0) * 100)}%")

    # Top 组合
    top = report.get("top_combinations", [])
    if top:
        click.echo(click.style("\n最佳参数组合:", fg="green", bold=True))
        for i, c in enumerate(top, 1):
            parts = []
            if c.get("style"):
                parts.append(c["style"])
            if c.get("tone"):
                parts.append(c["tone"])
            if c.get("length"):
                parts.append(c["length"])
            click.echo(f"  {i}. {' + '.join(parts) or '-'} | 评分 {c.get('avg_rating', 0)} | {c.get('count', 0)} 次")

    # Worst 组合
    worst = report.get("worst_combinations", [])
    if worst:
        click.echo(click.style("\n低分参数组合:", fg="red", bold=True))
        for i, c in enumerate(worst, 1):
            parts = []
            if c.get("style"):
                parts.append(c["style"])
            if c.get("tone"):
                parts.append(c["tone"])
            if c.get("length"):
                parts.append(c["length"])
            click.echo(f"  {i}. {' + '.join(parts) or '-'} | 评分 {c.get('avg_rating', 0)} | {c.get('count', 0)} 次")

    # 优化建议
    suggestions = report.get("optimization_suggestions", [])
    if suggestions:
        click.echo(click.style("\n💡 优化建议:", fg="yellow", bold=True))
        for i, s in enumerate(suggestions, 1):
            click.echo(f"  {i}. {s}")

    click.echo()


def format_config(cfg):
    """格式化配置显示"""
    click.echo(click.style("\n⚙️  当前配置 (~/.xhs-creator/config.yaml)\n", fg="cyan", bold=True))

    llm = cfg.get("llm", {})
    click.echo(click.style("LLM:", fg="yellow", bold=True))
    click.echo(f"  api_url:     {llm.get('api_url', '-')}")
    click.echo(f"  model:       {llm.get('model', '-')}")
    click.echo(f"  temperature: {llm.get('temperature', '-')}")
    click.echo(f"  timeout:     {llm.get('timeout', '-')}秒")

    api_key = llm.get("api_key", "")
    if api_key:
        masked = api_key[:6] + "***" + api_key[-4:] if len(api_key) > 10 else "***"
        click.echo(f"  api_key:     {masked}")
    else:
        click.echo("  api_key:     (未配置)")

    defaults = cfg.get("defaults", {})
    click.echo(click.style("\n默认风格:", fg="yellow", bold=True))
    click.echo(f"  风格: {defaults.get('style', '-')}")
    click.echo(f"  语气: {defaults.get('tone', '-')}")
    click.echo(f"  篇幅: {defaults.get('length', '-')}")
    click.echo(f"  emoji: {'是' if defaults.get('emoji') else '否'}")
    click.echo(f"  标题字数上限: {defaults.get('max_title_length', '-')}")

    domains = cfg.get("domains", {})
    click.echo(click.style("\n领域偏好:", fg="yellow", bold=True))
    click.echo(f"  主要领域: {domains.get('primary', '-') or '(未设置)'}")
    secondary = domains.get("secondary", [])
    if secondary:
        click.echo(f"  关注领域: {', '.join(secondary)}")
    custom_tags = domains.get("custom_tags", [])
    if custom_tags:
        click.echo(f"  自定义标签: {', '.join(custom_tags)}")
    click.echo(f"  自动选题: {'是' if domains.get('auto_topic') else '否'}")

    image_gen = cfg.get("image_gen", {})
    click.echo(click.style("\n图片生成:", fg="yellow", bold=True))
    click.echo(f"  启用: {'是' if image_gen.get('enabled') else '否'}")
    click.echo(f"  模型: {image_gen.get('model', '-')}")
    click.echo(f"  风格: {image_gen.get('style', '-')}")

    xhs = cfg.get("xhs", {})
    click.echo(click.style("\n小红书 MCP:", fg="yellow", bold=True))
    click.echo(f"  端口: {xhs.get('mcp_port', '-')}")
    click.echo(f"  自动启动: {'是' if xhs.get('auto_start') else '否'}")

    output = cfg.get("output", {})
    click.echo(click.style("\n输出设置:", fg="yellow", bold=True))
    click.echo(f"  格式: {output.get('format', '-')}")
    click.echo(f"  彩色: {'是' if output.get('color') else '否'}")
    click.echo(f"  保存历史: {'是' if output.get('save_history') else '否'}")

    click.echo()
