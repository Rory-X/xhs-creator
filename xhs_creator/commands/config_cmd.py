"""config - 配置管理命令"""

import click

from ..config import (
    CONFIG_FILE,
    get_value,
    load_config,
    reset_config,
    save_config,
    set_value,
)
from ..formatter import format_config, output_json


@click.group()
def config():
    """管理 xhs-creator 配置"""
    pass


@config.command()
@click.option("--json", "json_mode", is_flag=True, help="以 JSON 格式输出")
def show(json_mode):
    """显示当前配置"""
    cfg = load_config()

    if json_mode:
        output_json(cfg)
    else:
        format_config(cfg)


@config.command("set")
@click.argument("key")
@click.argument("value")
def set_cmd(key, value):
    """设置配置项（支持点号路径，如 llm.model）"""
    old = get_value(key)
    new_value = set_value(key, value)

    click.echo(click.style(f"✅ 已更新: {key}", fg="green"))
    if old is not None:
        click.echo(f"   {old} → {new_value}")
    else:
        click.echo(f"   → {new_value}")


@config.command()
@click.confirmation_option(prompt="确定要恢复默认配置吗？")
def reset():
    """恢复默认配置"""
    reset_config()
    click.echo(click.style("✅ 配置已恢复为默认值", fg="green"))


@config.command()
def init():
    """交互式初始化配置"""
    click.echo(click.style("\n🔧 xhs-creator 配置初始化\n", fg="cyan", bold=True))

    cfg = load_config()

    # LLM 配置
    click.echo(click.style("── LLM API 配置 ──", fg="yellow"))

    api_key = click.prompt(
        "  API Key",
        default=cfg["llm"]["api_key"] or "",
        show_default=bool(cfg["llm"]["api_key"]),
    )
    cfg["llm"]["api_key"] = api_key

    model = click.prompt(
        "  模型",
        default=cfg["llm"]["model"],
    )
    cfg["llm"]["model"] = model

    temperature = click.prompt(
        "  Temperature (0-1)",
        default=cfg["llm"]["temperature"],
        type=float,
    )
    cfg["llm"]["temperature"] = temperature

    # 默认风格
    click.echo(click.style("\n── 默认内容风格 ──", fg="yellow"))

    style = click.prompt(
        "  写作风格 (种草/测评/教程/日常分享/干货)",
        default=cfg["defaults"]["style"],
    )
    cfg["defaults"]["style"] = style

    tone = click.prompt(
        "  语气 (活泼/专业/亲切/搞笑)",
        default=cfg["defaults"]["tone"],
    )
    cfg["defaults"]["tone"] = tone

    length = click.prompt(
        "  默认篇幅 (short/medium/long)",
        default=cfg["defaults"]["length"],
        type=click.Choice(["short", "medium", "long"]),
    )
    cfg["defaults"]["length"] = length

    # 领域偏好
    click.echo(click.style("\n── 领域偏好 ──", fg="yellow"))

    primary = click.prompt(
        "  主要创作领域",
        default=cfg["domains"].get("primary", "") or "",
    )
    cfg["domains"]["primary"] = primary

    secondary_str = click.prompt(
        "  其他关注领域 (逗号分隔)",
        default=",".join(cfg["domains"].get("secondary", [])),
    )
    cfg["domains"]["secondary"] = [s.strip() for s in secondary_str.split(",") if s.strip()]

    auto_topic = click.confirm(
        "  未指定关键词时自动从领域列表随机选题？",
        default=cfg["domains"].get("auto_topic", False),
    )
    cfg["domains"]["auto_topic"] = auto_topic

    # 保存
    save_config(cfg)

    click.echo(click.style(f"\n✅ 配置已保存到 {CONFIG_FILE}", fg="green", bold=True))
