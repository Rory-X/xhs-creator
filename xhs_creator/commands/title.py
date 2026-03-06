"""title - 标题优化命令"""

import click

from ..config import load_config
from ..formatter import format_parse_failure, format_titles, output_json
from ..llm import call_llm, parse_llm_json
from ..prompts import TITLE_SYSTEM_PROMPT


@click.command()
@click.argument("text")
@click.option("-n", "--count", default=5, help="生成标题数量")
@click.option("--style", default=None, help="标题风格（悬念/数字/情感/对比）")
@click.option("--emoji/--no-emoji", default=None, help="是否包含 emoji")
@click.option("--max-len", default=None, type=int, help="标题最大字数")
@click.option("--json", "json_mode", is_flag=True, help="以 JSON 格式输出")
def title(text, count, style, emoji, max_len, json_mode):
    """生成小红书风格的优化标题"""
    cfg = load_config()

    if style is None:
        style = cfg["defaults"]["style"]
    if emoji is None:
        emoji = cfg["defaults"]["emoji"]
    if max_len is None:
        max_len = cfg["defaults"]["max_title_length"]

    emoji_instruction = "标题中包含合适的 emoji 表情" if emoji else "标题中不使用 emoji"

    prompt = TITLE_SYSTEM_PROMPT.format(
        count=count,
        max_length=max_len,
        style=style,
        emoji_instruction=emoji_instruction,
    )

    if not json_mode:
        click.echo("正在生成标题...")

    result = call_llm(text, prompt)

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
        format_titles(data, text)
