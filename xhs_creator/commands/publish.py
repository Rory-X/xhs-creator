"""publish - 一键发布命令"""

import os
import time

import click

from ..config import load_config
from ..formatter import format_publish_preview, output_json
from ..md2xhs import md_to_xhs
from ..xhs_client import check_login, ensure_mcp_running, publish_note


def _generate_cover(title):
    """用 Pango + Cairo 生成封面图，原生支持彩色 emoji + 中文

    Args:
        title: 笔记标题（含 emoji）

    Returns:
        str: 生成的图片路径
    """
    import math

    import gi
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo
    import cairo

    width, height = 1080, 1440

    # 创建 Cairo surface
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)

    # 渐变背景：浅粉 (#FFE4EC) 到浅紫 (#E8D5F5)
    gradient = cairo.LinearGradient(0, 0, 0, height)
    gradient.add_color_stop_rgb(0, 255/255, 228/255, 236/255)  # 浅粉
    gradient.add_color_stop_rgb(1, 232/255, 213/255, 245/255)  # 浅紫
    ctx.set_source(gradient)
    ctx.rectangle(0, 0, width, height)
    ctx.fill()

    # Pango layout 用于渲染文字
    layout = PangoCairo.create_layout(ctx)

    # 根据标题长度动态选字号：短标题超大字，长标题适当缩小
    title_len = len(title)
    if title_len <= 8:
        font_size = 80
    elif title_len <= 14:
        font_size = 68
    elif title_len <= 20:
        font_size = 58
    else:
        font_size = 48

    # 字体：Noto Sans CJK Bold + emoji fallback
    font_desc = Pango.FontDescription.from_string(f"Noto Sans CJK SC Bold {font_size}")
    layout.set_font_description(font_desc)

    # 设置换行：居中对齐，限制宽度
    max_text_width = width - 120  # 左右各留 60px
    layout.set_width(max_text_width * Pango.SCALE)
    layout.set_alignment(Pango.Alignment.CENTER)
    layout.set_wrap(Pango.WrapMode.CHAR)
    layout.set_line_spacing(1.5)

    # 设置标题文本
    layout.set_text(title, -1)

    # 获取文字实际尺寸
    ink_rect, logical_rect = layout.get_pixel_extents()
    text_w = logical_rect.width
    text_h = logical_rect.height

    # 垂直居中
    x = (width - text_w) / 2 - logical_rect.x
    y = (height - text_h) / 2 - logical_rect.y

    ctx.move_to(x, y)

    # 文字颜色
    ctx.set_source_rgb(80/255, 40/255, 80/255)
    PangoCairo.show_layout(ctx, layout)

    # 底部装饰线
    line_y = (height + text_h) / 2 + 40
    line_w = 200
    ctx.set_source_rgb(180/255, 140/255, 200/255)
    ctx.set_line_width(3)
    ctx.move_to((width - line_w) / 2, line_y)
    ctx.line_to((width + line_w) / 2, line_y)
    ctx.stroke()

    # 保存为 PNG 再转 JPG（Cairo 原生输出 PNG）
    ts = int(time.time())
    png_path = f"/tmp/xhs-creator-cover-{ts}.png"
    jpg_path = f"/tmp/xhs-creator-cover-{ts}.jpg"
    surface.write_to_png(png_path)

    # 转 JPG（小红书更友好）
    try:
        from PIL import Image
        img = Image.open(png_path).convert("RGB")
        img.save(jpg_path, "JPEG", quality=92)
        os.remove(png_path)
        return jpg_path
    except Exception:
        # fallback: 直接用 PNG
        return png_path


def _generate_cover_via_api(title, image_gen_cfg):
    """通过图片生成 API 生成封面

    Args:
        title: 笔记标题
        image_gen_cfg: image_gen 配置字典

    Returns:
        str: 图片路径，失败返回 None
    """
    import base64
    import json
    import urllib.request
    import urllib.error

    api_url = image_gen_cfg.get("api_url", "")
    api_key = image_gen_cfg.get("api_key", "")
    model = image_gen_cfg.get("model", "")
    style = image_gen_cfg.get("style", "小红书风格，色彩鲜明，扁平插画")

    if not api_url or not api_key or not model:
        return None

    prompt = f"为小红书笔记生成一张封面配图，标题是「{title}」，风格要求：{style}，竖版3:4比例"

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # 尝试从响应中提取 base64 图片
        choices = data.get("choices", [])
        if not choices:
            return None

        message = choices[0].get("message", {})
        content = message.get("content", "")

        # 检查是否有 inline image（base64）
        if "data:image" in content:
            import re
            match = re.search(r'data:image/(\w+);base64,([A-Za-z0-9+/=]+)', content)
            if match:
                ext = match.group(1)
                img_data = base64.b64decode(match.group(2))
                ts = int(time.time())
                path = f"/tmp/xhs-creator-cover-{ts}.{ext}"
                with open(path, "wb") as f:
                    f.write(img_data)
                return path

        return None

    except Exception:
        return None


@click.command()
@click.option("--title", "-t", required=True, help="笔记标题（≤20字）")
@click.option("--content", "-c", required=True, help="笔记正文（≤1000字）")
@click.option("--images", "-i", default=None, help="图片路径，逗号分隔")
@click.option("--cards", is_flag=True, help="将内容转为多张卡片图发布（推荐！）")
@click.option("--theme", default="tech", type=click.Choice(["tech", "warm", "fresh"]), help="卡片主题")
@click.option("--draft", is_flag=True, help="保存为草稿")
@click.option("--confirm/--no-confirm", default=True, help="发布前确认")
@click.option("--json", "json_mode", is_flag=True, help="以 JSON 格式输出")
def publish(title, content, images, cards, theme, draft, confirm, json_mode):
    """将内容发布到小红书"""
    cfg = load_config()
    max_title_len = cfg["defaults"]["max_title_length"]

    # 校验标题长度
    if len(title) > max_title_len:
        click.echo(
            click.style(f"❌ 标题超过 {max_title_len} 字限制 (当前 {len(title)} 字)", fg="red"),
            err=True,
        )
        raise SystemExit(1)

    # 校验正文长度（卡片模式不限制，内容在图片上）
    if not cards and len(content) > 1000:
        click.echo(
            click.style(f"❌ 正文超过 1000 字限制 (当前 {len(content)} 字)", fg="red"),
            err=True,
        )
        raise SystemExit(1)

    # Markdown → 小红书纯文本
    original_content = content
    content = md_to_xhs(content)
    if content != original_content and not json_mode:
        click.echo(click.style("📝 已将 Markdown 转换为小红书格式", fg="cyan"))

    # 卡片图模式
    if cards:
        from ..content2cards import content_to_cards
        if not json_mode:
            click.echo(click.style(f"🎨 正在生成卡片图（{theme} 主题）...", fg="cyan"))
        card_paths = content_to_cards(title, original_content, theme)
        image_list = card_paths
        if not json_mode:
            click.echo(click.style(f"✅ 生成 {len(card_paths)} 张卡片图", fg="green"))
            for p in card_paths:
                click.echo(f"   📄 {p}")
    else:
        # 处理图片路径（原有逻辑）
        image_list = None
        if images:
            image_list = [p.strip() for p in images.split(",")]
            for img_path in image_list:
                if not os.path.exists(img_path):
                    click.echo(click.style(f"❌ 图片不存在: {img_path}", fg="red"), err=True)
                    raise SystemExit(1)

        # 无图片时自动生成封面
        if not image_list:
            image_gen_cfg = cfg.get("image_gen", {})
            if image_gen_cfg.get("enabled", False):
                cover_path = _generate_cover_via_api(title, image_gen_cfg)
                if cover_path:
                    image_list = [cover_path]
                    if not json_mode:
                        click.echo(click.style(f"🎨 已通过 API 生成封面: {cover_path}", fg="green"))
                else:
                    if not json_mode:
                        click.echo(click.style("⚠ API 生成封面失败，使用本地生成", fg="yellow"))
                    cover_path = _generate_cover(title)
                    image_list = [cover_path]
                    if not json_mode:
                        click.echo(click.style(f"🖼  已自动生成封面: {cover_path}", fg="green"))
            else:
                cover_path = _generate_cover(title)
                image_list = [cover_path]
                if not json_mode:
                    click.echo(click.style(f"🖼  已自动生成封面: {cover_path}", fg="green"))

    # 确保 MCP 服务运行
    mcp_status = ensure_mcp_running()
    if "error" in mcp_status:
        click.echo(click.style(f"❌ {mcp_status['error']}", fg="red"), err=True)
        raise SystemExit(1)

    # 检查登录状态
    login_result = check_login()
    if "error" in login_result:
        click.echo(click.style(f"⚠ 登录状态检查失败: {login_result['error']}", fg="yellow"))

    # 发布预览与确认
    if confirm and not json_mode:
        format_publish_preview(title, content, image_list)
        if not click.confirm("确认发布？"):
            click.echo("已取消发布")
            return

    # 发布
    if not json_mode:
        action = "保存草稿" if draft else "发布"
        click.echo(f"正在{action}...")

    result = publish_note(title, content, image_list)

    if "error" in result:
        click.echo(click.style(f"❌ 发布失败: {result['error']}", fg="red"), err=True)
        raise SystemExit(1)

    if json_mode:
        output_json({"success": True, "message": result.get("content", "发布成功")})
    else:
        click.echo(click.style("\n✅ 发布成功！", fg="green", bold=True))
        if result.get("content"):
            click.echo(result["content"])
