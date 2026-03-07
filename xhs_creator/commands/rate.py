"""rate - 评分反馈命令"""

import click

from ..tracker import add_feedback, get_last_trace_id


@click.command()
@click.argument("score", type=int, required=False, default=None)
@click.option("--adopt", is_flag=True, help="标记为采用")
@click.option("--drop", is_flag=True, help="标记为废弃")
@click.option("--trace", "trace_id", default=None, help="指定 trace_id")
def rate(score, adopt, drop, trace_id):
    """对最近一次生成结果评分 (1-5)"""
    # 1. 确定 trace_id
    if not trace_id:
        trace_id = get_last_trace_id()
        if not trace_id:
            click.echo(click.style("没有找到最近的调用记录", fg="red"), err=True)
            raise SystemExit(1)

    # 2. 验证 score
    if score is not None and not (1 <= score <= 5):
        click.echo(click.style("评分范围: 1-5", fg="red"), err=True)
        raise SystemExit(1)

    # 3. 至少需要提供一个操作
    if score is None and not adopt and not drop:
        click.echo(click.style("请提供评分 (1-5) 或 --adopt/--drop", fg="red"), err=True)
        raise SystemExit(1)

    # 4. 确定 adopted
    adopted = None
    if adopt:
        adopted = True
    elif drop:
        adopted = False

    # 5. 更新
    ok = add_feedback(trace_id, rating=score, adopted=adopted)
    if not ok:
        click.echo(click.style(f"未找到 trace: {trace_id}", fg="red"), err=True)
        raise SystemExit(1)

    # 6. 输出确认
    parts = []
    if score:
        parts.append("评分 " + "⭐" * score)
    if adopted is True:
        parts.append("已采用")
    elif adopted is False:
        parts.append("已废弃")
    click.echo(click.style(f"已更新: {' | '.join(parts)} ({trace_id})", fg="green"))
