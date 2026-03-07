"""recommend - 话题推荐命令组"""

import click

from ..formatter import output_json
from ..recommender.engine import Recommender


@click.group("recommend", invoke_without_command=True)
@click.option("-n", "--count", default=5, help="推荐数量")
@click.option("--domain", default=None, help="限定领域")
@click.option("--explore", is_flag=True, help="探索模式（含跨领域推荐）")
@click.option("--refresh", is_flag=True, help="强制刷新（忽略缓存）")
@click.option("--json", "json_mode", is_flag=True, help="JSON 输出")
@click.pass_context
def recommend(ctx, count, domain, explore, refresh, json_mode):
    """获取今日话题推荐"""
    if ctx.invoked_subcommand is not None:
        return

    engine = Recommender()

    # 检查缓存
    if not refresh:
        cached = engine.get_cached_recommendations()
        if cached:
            if json_mode:
                output_json({"recommendations": cached[:count]})
            else:
                click.echo(click.style("(使用缓存，--refresh 可刷新)\n", fg="bright_black"))
                _display_recommendations(cached[:count])
            return

    if not json_mode:
        click.echo("正在生成推荐...")

    recommendations = engine.generate_recommendations(
        n=count, domain=domain, explore=explore, refresh=refresh,
    )

    if json_mode:
        output_json({"recommendations": recommendations})
    else:
        if not recommendations:
            click.echo(click.style("暂无推荐结果，请检查配置或网络连接", fg="yellow"))
            return
        _display_recommendations(recommendations)


@recommend.command("pick")
@click.argument("index", type=int)
@click.option("--title", "gen_title", is_flag=True, help="直接生成标题")
@click.option("--write", "gen_write", is_flag=True, help="直接生成正文")
def pick(index, gen_title, gen_write):
    """选择推荐话题进入创作流程"""
    engine = Recommender()
    rec = engine.pick_recommendation(index)
    if not rec:
        click.echo(click.style("未找到第 {} 条推荐".format(index), fg="red"), err=True)
        raise SystemExit(1)

    topic_text = rec["topic"]
    click.echo(click.style("已选择: {}".format(topic_text), fg="green"))

    if gen_title:
        from .title import title
        ctx = click.Context(title)
        ctx.invoke(title, text=topic_text)
    elif gen_write:
        from .write import write
        ctx = click.Context(write)
        ctx.invoke(write, topic=topic_text)
    else:
        click.echo("\n可继续执行:")
        click.echo('  xhs-creator title "{}"'.format(topic_text))
        click.echo('  xhs-creator write -t "{}"'.format(topic_text))


@recommend.command("like")
@click.argument("index", type=int)
def like(index):
    """对推荐点赞"""
    engine = Recommender()
    rec = engine.pick_recommendation(index)
    if rec:
        engine.feedback(rec.get("id", "rec_{:03d}".format(index)), liked=True)
        click.echo(click.style("已点赞", fg="green"))
    else:
        click.echo(click.style("未找到第 {} 条推荐".format(index), fg="red"), err=True)


@recommend.command("dislike")
@click.argument("index", type=int)
def dislike(index):
    """对推荐踩"""
    engine = Recommender()
    rec = engine.pick_recommendation(index)
    if rec:
        engine.feedback(rec.get("id", "rec_{:03d}".format(index)), liked=False)
        click.echo(click.style("已标记不感兴趣", fg="yellow"))
    else:
        click.echo(click.style("未找到第 {} 条推荐".format(index), fg="red"), err=True)


def _display_recommendations(recs):
    # type: (list) -> None
    """格式化输出推荐列表"""
    click.echo(click.style("\n💡 今日推荐 ({} 条)\n".format(len(recs)), fg="cyan", bold=True))
    for i, rec in enumerate(recs, 1):
        heat = "🔥" * min(rec.get("heat_score", 0), 5)
        click.echo(click.style(
            "  {}. {}".format(i, rec.get("topic", "")),
            fg="bright_white", bold=True,
        ))
        click.echo("     {}  风格: {}  语气: {}".format(
            heat, rec.get("suggested_style", "-"), rec.get("suggested_tone", "-"),
        ))
        click.echo("     💬 {}".format(rec.get("reason", "")))
        tags = rec.get("tags", [])
        if tags:
            click.echo("     {}".format(" ".join("#" + t for t in tags)))
        click.echo()
