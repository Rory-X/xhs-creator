"""trends - 趋势查看命令"""

import click

from ..config import load_config
from ..formatter import output_json
from ..recommender.trends import collect_trends


@click.command("trends")
@click.argument("domain", required=False, default=None)
@click.option("--refresh", is_flag=True, help="强制刷新趋势数据")
@click.option("--json", "json_mode", is_flag=True, help="JSON 输出")
def trends(domain, refresh, json_mode):
    """查看各领域当前趋势"""
    cfg = load_config()

    if domain:
        domains = [domain]
    else:
        # 使用配置的所有领域
        d = cfg.get("domains", {})
        domains = []
        if d.get("primary"):
            domains.append(d["primary"])
        domains.extend(d.get("secondary", []))
        domains.extend(cfg.get("recommend", {}).get("auto_collect_domains", []))

    if not domains:
        click.echo(click.style(
            '未配置领域，请指定: xhs-creator trends "AI"',
            fg="yellow",
        ))
        return

    if not json_mode:
        click.echo("正在获取趋势数据...")

    all_trends = collect_trends(domains, force_refresh=refresh)

    if not all_trends:
        click.echo(click.style("未获取到趋势数据，请检查 MCP 服务是否运行", fg="yellow"))
        return

    if json_mode:
        output_json(all_trends)
    else:
        _format_trends(all_trends)


def _format_trends(all_trends):
    # type: (dict) -> None
    """格式化趋势输出"""
    for domain, data in all_trends.items():
        click.echo(click.style(
            "\n📈 {} 领域趋势".format(domain), fg="cyan", bold=True,
        ))

        for topic in data.get("hot_topics", [])[:5]:
            trend_icon = {
                "rising": "📈",
                "stable": "➡️",
                "declining": "📉",
            }.get(topic.get("trend"), "")
            click.echo("  {} {}  提及 {}次  均赞 {}".format(
                trend_icon, topic.get("keyword", ""),
                topic.get("mention_count", "-"),
                topic.get("avg_likes", "-"),
            ))

        tags = data.get("hot_tags", [])
        if tags:
            click.echo("  热门标签: {}".format(" ".join("#" + t for t in tags[:8])))

        click.echo()
