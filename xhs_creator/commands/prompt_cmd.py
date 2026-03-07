"""prompt - Prompt 模板管理命令组"""

import click

from ..formatter import output_json
from ..optimizer import (
    TEMPLATE_NAMES,
    get_current_prompt,
    list_versions,
    reset_to_default,
    rollback,
)
from ..prompts import BUILTIN_PROMPTS


# 命令名到模板名映射
CMD_TO_TEMPLATE = {
    "topic": "TOPIC_SYSTEM_PROMPT",
    "title": "TITLE_SYSTEM_PROMPT",
    "write": "WRITE_SYSTEM_PROMPT",
    "analyze": "ANALYZE_SYSTEM_PROMPT",
}

VALID_COMMANDS = list(CMD_TO_TEMPLATE.keys())


@click.group("prompt")
def prompt_group():
    """管理 Prompt 模板"""
    pass


@prompt_group.command("show")
@click.argument("command_name", type=click.Choice(VALID_COMMANDS))
def show(command_name):
    """查看当前 prompt 模板"""
    template = CMD_TO_TEMPLATE[command_name]
    content = get_current_prompt(template)
    source = "自定义版本"
    if content is None:
        content = BUILTIN_PROMPTS[template]
        source = "内置默认"
    click.echo(click.style(
        "\n[{}] prompt ({}):\n".format(command_name, source),
        fg="cyan", bold=True,
    ))
    click.echo(content)


@prompt_group.command("versions")
@click.argument("command_name", type=click.Choice(VALID_COMMANDS))
def versions_cmd(command_name):
    """查看 prompt 版本历史"""
    template = CMD_TO_TEMPLATE[command_name]
    vers = list_versions(template)
    if not vers:
        click.echo("暂无版本历史（使用内置默认）")
        return
    for v in vers:
        marker = " (当前)" if v.get("is_current") else ""
        click.echo("  {}{}  {}  {}".format(
            v["version"], marker, v["created_at"], v.get("change_summary", "")
        ))


@prompt_group.command("rollback")
@click.argument("command_name", type=click.Choice(VALID_COMMANDS))
@click.argument("version", required=False, default=None)
def rollback_cmd(command_name, version):
    """回滚到上一版本或指定版本"""
    template = CMD_TO_TEMPLATE[command_name]
    try:
        result = rollback(template, version)
        click.echo(click.style("已回滚到 {}".format(result), fg="green"))
    except ValueError as e:
        click.echo(click.style(str(e), fg="red"), err=True)
        raise SystemExit(1)


@prompt_group.command("reset")
@click.argument("command_name", type=click.Choice(VALID_COMMANDS))
@click.confirmation_option(prompt="确定恢复为内置默认 prompt？")
def reset(command_name):
    """恢复为内置默认 prompt"""
    template = CMD_TO_TEMPLATE[command_name]
    reset_to_default(template)
    click.echo(click.style("已恢复为内置默认", fg="green"))


@prompt_group.command("optimize")
@click.argument("command_name", type=click.Choice(VALID_COMMANDS), required=False)
def optimize(command_name):
    """分析数据并生成优化建议（Phase 5 实现）"""
    click.echo("此功能将在后续版本实现")


@prompt_group.command("apply")
@click.argument("command_name", type=click.Choice(VALID_COMMANDS))
def apply_cmd(command_name):
    """应用最新优化建议（Phase 5 实现）"""
    click.echo("此功能将在后续版本实现")
