"""CLI 入口 - 注册所有子命令"""

import click

from . import __version__
from .commands.analyze import analyze
from .commands.config_cmd import config
from .commands.publish import publish
from .commands.title import title
from .commands.topic import topic
from .commands.write import write


@click.group()
@click.version_option(version=__version__, prog_name="xhs-creator")
def cli():
    """🔴 小红书内容创作 CLI 工具

    AI 驱动的小红书内容生成、分析和发布工具。

    \b
    常用命令:
      topic    根据关键词生成选题建议
      title    生成小红书风格标题
      write    自动生成小红书正文
      analyze  分析竞品笔记特征
      publish  发布内容到小红书
      config   管理配置
    """
    pass


cli.add_command(topic)
cli.add_command(title)
cli.add_command(write)
cli.add_command(analyze)
cli.add_command(publish)
cli.add_command(config)


if __name__ == "__main__":
    cli()
