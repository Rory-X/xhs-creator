"""write - 正文撰写命令"""

import click

from ..config import load_config
from ..formatter import format_article, format_parse_failure, output_json
from ..llm import call_llm, parse_llm_json
from ..prompts import LENGTH_DESC, WRITE_SYSTEM_PROMPT


@click.command()
@click.option("--topic", "-t", default=None, help="选题内容或标题（未指定时使用默认领域）")
@click.option("--style", default=None, help="写作风格（种草/测评/教程/日常分享/干货）")
@click.option("--tone", default=None, help="语气（活泼/专业/亲切/搞笑）")
@click.option(
    "--length", "length", default=None,
    type=click.Choice(["short", "medium", "long"]),
    help="篇幅（short/medium/long）",
)
@click.option("--tags", default=None, help="自定义话题标签，逗号分隔")
@click.option("--image-tips/--no-image-tips", default=True, help="附带图片建议（默认开启）")
@click.option("--json", "json_mode", is_flag=True, help="以 JSON 格式输出")
def write(topic, style, tone, length, tags, image_tips, json_mode):
    """根据选题自动生成小红书正文"""
    cfg = load_config()

    # 未指定 topic 时，从 domains.primary 获取
    if not topic:
        primary = cfg.get("domains", {}).get("primary", "")
        if primary:
            topic = primary
            if not json_mode:
                click.echo(click.style(f"📌 使用默认领域: {topic}", fg="cyan"))
        else:
            click.echo(click.style("❌ 未指定选题，请通过 --topic 指定或配置 domains.primary", fg="red"), err=True)
            raise SystemExit(1)

    if style is None:
        style = cfg["defaults"]["style"]
    if tone is None:
        tone = cfg["defaults"]["tone"]
    if length is None:
        length = cfg["defaults"]["length"]

    length_desc = LENGTH_DESC.get(length, LENGTH_DESC["medium"])

    if tags:
        tags_instruction = f"使用以下话题标签：{tags}"
    else:
        tags_instruction = "自动生成合适的话题标签"

    if image_tips:
        image_tips_instruction = "请同时提供配图建议（封面文案和配图风格）。"
    else:
        image_tips_instruction = "image_tips 字段返回空对象 {{}}"

    prompt = WRITE_SYSTEM_PROMPT.format(
        style=style,
        tone=tone,
        length_desc=length_desc,
        tags_instruction=tags_instruction,
        image_tips_instruction=image_tips_instruction,
    )

    if not json_mode:
        click.echo("正在生成正文...")

    result = call_llm(topic, prompt)

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
        format_article(data)
