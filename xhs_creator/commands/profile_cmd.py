"""profile - 用户画像管理命令组"""

import click

from ..formatter import output_json
from ..recommender.profile import (
    add_domain,
    build_profile,
    load_profile,
    remove_domain,
)


@click.group("profile")
def profile_group():
    """管理用户兴趣画像"""
    pass


@profile_group.command("show")
@click.option("--json", "json_mode", is_flag=True, help="JSON 输出")
def show(json_mode):
    """查看当前画像"""
    profile = load_profile()
    if json_mode:
        output_json(profile)
    else:
        _format_profile(profile)


@profile_group.command("refresh")
def refresh():
    """基于最新数据重建画像"""
    profile = build_profile(force_rebuild=True)
    click.echo(click.style("画像已更新", fg="green"))
    _format_profile(profile)


@profile_group.command("add-domain")
@click.argument("domain")
def add_domain_cmd(domain):
    """添加感兴趣领域"""
    add_domain(domain)
    click.echo(click.style("已添加: {}".format(domain), fg="green"))


@profile_group.command("remove-domain")
@click.argument("domain")
def remove_domain_cmd(domain):
    """移除领域"""
    remove_domain(domain)
    click.echo(click.style("已移除: {}".format(domain), fg="green"))


def _format_profile(profile):
    # type: (dict) -> None
    """格式化画像输出"""
    click.echo(click.style("\n👤 用户画像\n", fg="cyan", bold=True))

    interests = profile.get("interests", {})
    primary = interests.get("primary", "")
    if primary:
        click.echo(click.style("主要领域:", fg="yellow", bold=True))
        click.echo("  {}".format(primary))

    domains = interests.get("domains", {})
    if domains:
        click.echo(click.style("\n兴趣领域:", fg="yellow", bold=True))
        for name, info in sorted(domains.items(), key=lambda x: x[1].get("weight", 0), reverse=True):
            weight = info.get("weight", 0)
            source = info.get("source", "")
            bar = "█" * int(weight * 10) + "░" * (10 - int(weight * 10))
            click.echo("  {} {} {:.1f} ({})".format(name, bar, weight, source))

    style_pref = profile.get("style_preference", {})
    preferred = style_pref.get("preferred", [])
    avoid = style_pref.get("avoid", [])
    if preferred or avoid:
        click.echo(click.style("\n风格偏好:", fg="yellow", bold=True))
        if preferred:
            click.echo("  偏好: {}".format(", ".join(preferred)))
        if avoid:
            click.echo("  避免: {}".format(", ".join(avoid)))

    created = profile.get("created_topics", [])
    if created:
        click.echo(click.style("\n已创作话题 (最近 {}):".format(min(len(created), 10)), fg="yellow", bold=True))
        for item in created[-10:]:
            topic = item.get("topic", "")
            date = item.get("date", "")
            rating = item.get("rating")
            rating_str = " ⭐" * rating if rating else ""
            click.echo("  {} {}{}".format(date, topic, rating_str))

    updated = profile.get("updated_at", "")
    if updated:
        click.echo(click.style("\n更新时间: {}".format(updated[:19]), fg="bright_black"))

    click.echo()
