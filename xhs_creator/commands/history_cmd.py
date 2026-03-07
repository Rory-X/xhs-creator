"""history - 调用历史查看命令"""

import click

from ..formatter import format_history_table, output_json
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

    format_history_table(traces)
