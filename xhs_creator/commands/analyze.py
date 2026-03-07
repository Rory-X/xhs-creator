"""analyze - 竞品分析命令"""

import click

from ..formatter import format_analysis, format_parse_failure, output_json
from ..llm import call_llm, parse_llm_json
from ..prompts import get_prompt
from ..xhs_client import ensure_mcp_running, search_notes


@click.command()
@click.argument("keyword")
@click.option("-n", "--limit", default=10, help="分析笔记数量")
@click.option(
    "--sort", default="hot",
    type=click.Choice(["hot", "new"]),
    help="排序方式（hot: 热度 / new: 最新）",
)
@click.option("--detail", is_flag=True, help="输出详细分析（含每条笔记摘要）")
@click.option("--no-track", is_flag=True, help="本次不记录调用历史")
@click.option("--prompt-version", default=None, help="使用指定版本 prompt")
@click.option("--json", "json_mode", is_flag=True, help="以 JSON 格式输出")
def analyze(keyword, limit, sort, detail, no_track, prompt_version, json_mode):
    """搜索分析小红书同类笔记的爆款特征"""
    # 确保 MCP 服务运行
    mcp_status = ensure_mcp_running()
    if "error" in mcp_status:
        click.echo(click.style(f"❌ {mcp_status['error']}", fg="red"), err=True)
        raise SystemExit(1)

    # 搜索笔记
    if not json_mode:
        click.echo(f'正在搜索 "{keyword}" 相关笔记...')

    search_result = search_notes(keyword, limit=limit)
    if "error" in search_result:
        click.echo(click.style(f"❌ 搜索失败: {search_result['error']}", fg="red"), err=True)
        raise SystemExit(1)

    search_context = search_result.get("content", "")

    if not search_context:
        click.echo(click.style("⚠ 未搜索到相关笔记", fg="yellow"))
        return

    # 构造分析 prompt 并调用 LLM
    prompt = get_prompt(
        "ANALYZE_SYSTEM_PROMPT",
        version=prompt_version,
        keyword=keyword,
        search_context=search_context,
    )

    if not json_mode:
        click.echo("正在分析笔记特征...")

    result = call_llm(
        f"分析关于「{keyword}」的小红书笔记", prompt,
        track=not no_track,
        command="analyze",
        options={"keyword": keyword, "limit": limit},
        prompt_info={"template_name": "ANALYZE_SYSTEM_PROMPT", "template_version": prompt_version or "builtin"},
    )

    if "error" in result:
        click.echo(click.style(f"❌ 错误: {result['error']}", fg="red"), err=True)
        raise SystemExit(1)

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
        format_analysis(data)
