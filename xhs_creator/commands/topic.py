"""topic - 选题生成命令"""

import random

import click

from ..config import load_config
from ..formatter import format_parse_failure, format_topics, output_json
from ..llm import call_llm, parse_llm_json
from ..prompts import TOPIC_SYSTEM_PROMPT, get_prompt
from ..xhs_client import ensure_mcp_running, search_notes


@click.command()
@click.argument("keyword", required=False, default=None)
@click.option("-n", "--count", default=5, help="生成选题数量")
@click.option("--style", default=None, help="内容风格（种草/测评/教程/日常分享）")
@click.option("--hot", is_flag=True, help="结合小红书热门趋势生成")
@click.option("--no-track", is_flag=True, help="本次不记录调用历史")
@click.option("--prompt-version", default=None, help="使用指定版本 prompt")
@click.option("--smart", is_flag=True, help="使用智能推荐引擎")
@click.option("--json", "json_mode", is_flag=True, help="以 JSON 格式输出")
def topic(keyword, count, style, hot, no_track, prompt_version, smart, json_mode):
    """根据关键词生成小红书选题建议

    KEYWORD 可选。未指定时使用配置的主要领域，或自动从领域列表随机选取。
    """
    cfg = load_config()

    # --smart 模式：使用推荐引擎
    if smart and not keyword:
        try:
            from ..recommender.engine import Recommender
            engine = Recommender()
            if not json_mode:
                click.echo(click.style("🧠 智能推荐模式...", fg="cyan"))
            recs = engine.generate_recommendations(n=count)
            if recs:
                # 转为 topic 格式输出
                data = {
                    "keyword": "智能推荐",
                    "topics": [
                        {
                            "title": r.get("topic", ""),
                            "angle": r.get("reason", ""),
                            "heat_score": r.get("heat_score", 3),
                            "tags": r.get("tags", []),
                        }
                        for r in recs
                    ],
                }
                if json_mode:
                    output_json(data)
                else:
                    format_topics(data, "智能推荐")
                return
            if not json_mode:
                click.echo(click.style("推荐引擎无结果，回退到普通模式", fg="yellow"))
        except Exception:
            if not json_mode:
                click.echo(click.style("推荐引擎不可用，回退到普通模式", fg="yellow"))

    # 未指定关键词时，从 domains 配置中获取
    if not keyword:
        domains = cfg.get("domains", {})
        auto_topic = domains.get("auto_topic", False)
        primary = domains.get("primary", "")
        secondary = domains.get("secondary", [])

        if auto_topic and (primary or secondary):
            # auto_topic 模式：从 primary + secondary 随机选一个
            candidates = []
            if primary:
                candidates.append(primary)
            candidates.extend(secondary)
            keyword = random.choice(candidates)
            if not json_mode:
                click.echo(click.style(f"🎲 自动选题领域: {keyword}", fg="cyan"))
        elif primary:
            keyword = primary
            if not json_mode:
                click.echo(click.style(f"📌 使用默认领域: {keyword}", fg="cyan"))
        else:
            # 提示用户输入
            keyword = click.prompt("请输入创作关键词/领域")
            if not keyword:
                click.echo(click.style("❌ 未指定关键词，请提供关键词或配置 domains.primary", fg="red"), err=True)
                raise SystemExit(1)

    if style is None:
        style = cfg["defaults"]["style"]

    # 可选：获取热门趋势数据
    hot_context = ""
    if hot:
        click.echo("正在搜索小红书热门笔记...")
        mcp_status = ensure_mcp_running()
        if "error" in mcp_status:
            click.echo(click.style(f"⚠ {mcp_status['error']}", fg="red"))
            click.echo("将不使用热门趋势数据，继续生成选题...")
        else:
            result = search_notes(keyword, limit=10)
            if "error" not in result:
                hot_context = (
                    f"\n以下是当前小红书上关于「{keyword}」的热门笔记参考：\n"
                    f"{result['content']}\n"
                    f"请参考这些热门内容的选题方向。\n"
                )
            else:
                click.echo(click.style(f"⚠ 搜索失败: {result['error']}", fg="red"))
                click.echo("将不使用热门趋势数据，继续生成选题...")

    # 构造 prompt 并调用 LLM
    prompt = get_prompt(
        "TOPIC_SYSTEM_PROMPT",
        version=prompt_version,
        count=count,
        style=style,
        hot_context=hot_context,
    )

    if not json_mode:
        click.echo("正在生成选题...")

    result = call_llm(
        keyword, prompt,
        track=not no_track,
        command="topic",
        options={"style": style, "count": count},
        prompt_info={"template_name": "TOPIC_SYSTEM_PROMPT", "template_version": prompt_version or "builtin"},
    )

    if "error" in result:
        click.echo(click.style(f"❌ 错误: {result['error']}", fg="red"), err=True)
        raise SystemExit(1)

    # 解析 LLM 返回的 JSON
    data = parse_llm_json(result["content"])
    if data is None:
        if json_mode:
            output_json({"content": result["content"], "parse_error": "无法解析为 JSON"})
        else:
            format_parse_failure(result["content"])
        return

    if json_mode:
        output_json(data)
    else:
        format_topics(data, keyword)
