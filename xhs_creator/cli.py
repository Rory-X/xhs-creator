"""CLI 入口 - 注册所有子命令"""

import click

from . import __version__
from .commands.analyze import analyze
from .commands.config_cmd import config
from .commands.history_cmd import history
from .commands.profile_cmd import profile_group
from .commands.prompt_cmd import prompt_group
from .commands.publish import publish
from .commands.rate import rate
from .commands.recommend_cmd import recommend
from .commands.stats import stats
from .commands.title import title
from .commands.topic import topic
from .commands.trends_cmd import trends
from .commands.write import write


@click.group()
@click.version_option(version=__version__, prog_name="xhs-creator")
def cli():
    """🔴 小红书内容创作 CLI 工具

    AI 驱动的小红书内容生成、分析和发布工具。

    \b
    常用命令:
      topic      根据关键词生成选题建议
      title      生成小红书风格标题
      write      自动生成小红书正文
      analyze    分析竞品笔记特征
      publish    发布内容到小红书
      config     管理配置

    \b
    反馈与分析:
      rate       对生成结果评分
      history    查看调用历史
      stats      查看创作统计
      prompt     管理 Prompt 模板

    \b
    智能推荐:
      recommend  获取智能话题推荐
      trends     查看各领域趋势
      profile    管理用户兴趣画像
    """
    pass


cli.add_command(topic)
cli.add_command(title)
cli.add_command(write)
cli.add_command(analyze)
cli.add_command(publish)
cli.add_command(config)
cli.add_command(rate)
cli.add_command(history)
cli.add_command(stats)
cli.add_command(prompt_group)
cli.add_command(recommend)
cli.add_command(trends)
cli.add_command(profile_group)


if __name__ == "__main__":
    cli()
