"""stats - 创作统计命令"""

import re
from datetime import datetime, timedelta

import click

from ..analyzer import generate_report
from ..formatter import format_stats_report, output_json


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


def _parse_last_period(period):
    # type: (str) -> str
    """'30d' -> ISO date 30 天前"""
    match = re.match(r"(\d+)d", period)
    if match:
        days = int(match.group(1))
        return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return None
