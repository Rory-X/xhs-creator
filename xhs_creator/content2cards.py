"""content2cards - 将文章内容拆分为多张小红书卡片图

小红书是图片平台，把长文内容做成精美的卡片式图片效果远比纯文字好。
支持：封面卡片 + 多张内容卡片 + 尾页卡片
"""

import math
import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo
import cairo


# ── 配色方案 ──
THEMES = {
    "tech": {
        "bg_start": (0.06, 0.07, 0.15),    # 深蓝黑
        "bg_end": (0.12, 0.10, 0.22),       # 深紫黑
        "title_color": (0.40, 0.85, 1.0),   # 科技蓝
        "text_color": (0.92, 0.92, 0.95),   # 亮白
        "accent": (0.55, 0.40, 1.0),        # 紫色
        "muted": (0.55, 0.55, 0.65),        # 灰色
        "bullet": (0.40, 0.85, 1.0),        # 蓝色
        "card_bg": (0.10, 0.11, 0.20),      # 卡片底色
        "tag_bg": (0.20, 0.15, 0.35),       # 标签底色
    },
    "warm": {
        "bg_start": (1.0, 0.96, 0.92),      # 暖白
        "bg_end": (0.98, 0.90, 0.85),       # 浅橙
        "title_color": (0.85, 0.35, 0.15),  # 橙红
        "text_color": (0.25, 0.22, 0.20),   # 深棕
        "accent": (0.90, 0.50, 0.20),       # 橙色
        "muted": (0.60, 0.55, 0.50),
        "bullet": (0.85, 0.35, 0.15),
        "card_bg": (1.0, 0.98, 0.95),
        "tag_bg": (0.95, 0.88, 0.82),
    },
    "fresh": {
        "bg_start": (0.93, 0.98, 0.95),     # 浅绿
        "bg_end": (0.85, 0.95, 0.90),       # 薄荷
        "title_color": (0.10, 0.55, 0.40),  # 深绿
        "text_color": (0.18, 0.20, 0.18),
        "accent": (0.20, 0.70, 0.50),
        "muted": (0.45, 0.55, 0.48),
        "bullet": (0.10, 0.55, 0.40),
        "card_bg": (0.96, 1.0, 0.97),
        "tag_bg": (0.85, 0.95, 0.88),
    },
}

# 默认主题
DEFAULT_THEME = "tech"

# 图片尺寸 (3:4 竖版，小红书推荐)
WIDTH = 1080
HEIGHT = 1440
PADDING = 80
CONTENT_WIDTH = WIDTH - PADDING * 2


@dataclass
class ContentBlock:
    """一个内容块"""
    type: str  # "heading", "text", "bullet", "numbered", "quote", "code", "tag"
    text: str
    level: int = 0  # heading level, numbered index


@dataclass
class Card:
    """一张卡片"""
    card_type: str  # "cover", "content", "end"
    title: str = ""
    blocks: List[ContentBlock] = field(default_factory=list)
    page_num: int = 0
    total_pages: int = 0


def parse_content(content: str) -> List[ContentBlock]:
    """解析文章内容为结构化块"""
    blocks = []
    lines = content.split("\n")
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 空行跳过
        if not line:
            i += 1
            continue
        
        # 标签行 (#tag1 #tag2)
        if re.match(r"^#\w", line) and not line.startswith("##"):
            # 检查是不是全是标签
            tags = re.findall(r"#(\w+)", line)
            if tags and all(f"#{t}" in line for t in tags):
                blocks.append(ContentBlock(type="tag", text=line))
                i += 1
                continue
        
        # Markdown 标题
        heading = re.match(r"^(#{1,4})\s+(.*)", line)
        if heading:
            level = len(heading.group(1))
            blocks.append(ContentBlock(type="heading", text=_clean_inline(heading.group(2)), level=level))
            i += 1
            continue
        
        # 无序列表
        bullet = re.match(r"^[-*+▪]\s+(.*)", line)
        if bullet:
            blocks.append(ContentBlock(type="bullet", text=_clean_inline(bullet.group(1))))
            i += 1
            continue
        
        # 有序列表
        numbered = re.match(r"^(\d+)[.)]\s+(.*)", line)
        if numbered:
            blocks.append(ContentBlock(type="numbered", text=_clean_inline(numbered.group(2)), level=int(numbered.group(1))))
            i += 1
            continue
        
        # 引用
        quote = re.match(r"^>\s*(.*)", line)
        if quote:
            blocks.append(ContentBlock(type="quote", text=_clean_inline(quote.group(1))))
            i += 1
            continue
        
        # 代码块
        if line.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append(ContentBlock(type="code", text="\n".join(code_lines)))
            i += 1
            continue
        
        # 普通文本
        blocks.append(ContentBlock(type="text", text=_clean_inline(line)))
        i += 1
    
    return blocks


def _clean_inline(text: str) -> str:
    """清理行内 markdown"""
    text = re.sub(r"\*{2,3}(.+?)\*{2,3}", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    return text


def _estimate_block_height(block: ContentBlock, layout: "PangoCairo.Layout", font_sizes: dict) -> int:
    """估算一个 block 渲染需要的高度"""
    if block.type == "heading":
        size = font_sizes.get("heading", 42)
        font = Pango.FontDescription.from_string(f"Noto Sans CJK SC Bold {size}")
        layout.set_font_description(font)
        layout.set_width(CONTENT_WIDTH * Pango.SCALE)
        layout.set_text(block.text, -1)
        _, lr = layout.get_pixel_extents()
        return lr.height + 20  # heading 额外间距
    
    elif block.type in ("text", "bullet", "numbered", "quote"):
        size = font_sizes.get("body", 32)
        font = Pango.FontDescription.from_string(f"Noto Sans CJK SC {size}")
        layout.set_font_description(font)
        w = CONTENT_WIDTH - (40 if block.type in ("bullet", "numbered") else 0)
        w = w - 60 if block.type == "quote" else w
        layout.set_width(w * Pango.SCALE)
        layout.set_text(block.text, -1)
        _, lr = layout.get_pixel_extents()
        return lr.height + 12
    
    elif block.type == "code":
        size = font_sizes.get("code", 26)
        font = Pango.FontDescription.from_string(f"Noto Sans Mono {size}")
        layout.set_font_description(font)
        layout.set_width((CONTENT_WIDTH - 60) * Pango.SCALE)
        layout.set_text(block.text, -1)
        _, lr = layout.get_pixel_extents()
        return lr.height + 40  # padding
    
    elif block.type == "tag":
        return 50
    
    return 40


def split_into_cards(title: str, blocks: List[ContentBlock], theme_name: str = DEFAULT_THEME) -> List[Card]:
    """把内容块拆分成多张卡片，每张不超过一页"""
    
    # 创建临时 surface 用于测量
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    layout = PangoCairo.create_layout(ctx)
    layout.set_wrap(Pango.WrapMode.CHAR)
    
    font_sizes = {"heading": 42, "body": 32, "code": 26}
    
    # 可用内容高度（去掉顶部/底部边距 + 页码区）
    usable_height = HEIGHT - PADDING * 2 - 80  # 80 for page indicator
    
    cards = []
    current_blocks = []
    current_height = 0
    
    # 分离标签块
    tag_blocks = [b for b in blocks if b.type == "tag"]
    content_blocks = [b for b in blocks if b.type != "tag"]
    
    for block in content_blocks:
        h = _estimate_block_height(block, layout, font_sizes)
        
        if current_height + h > usable_height and current_blocks:
            # 当前页满了，创建卡片
            cards.append(Card(card_type="content", blocks=current_blocks))
            current_blocks = []
            current_height = 0
        
        current_blocks.append(block)
        current_height += h
    
    # 最后一页
    if current_blocks:
        cards.append(Card(card_type="content", blocks=current_blocks))
    
    # 把标签加到最后一页
    if tag_blocks and cards:
        cards[-1].blocks.extend(tag_blocks)
    
    # 优化：如果最后一页内容太少（<50%高度），尝试合并到前一页
    if len(cards) >= 2:
        last_h = sum(_estimate_block_height(b, layout, font_sizes) for b in cards[-1].blocks)
        prev_h = sum(_estimate_block_height(b, layout, font_sizes) for b in cards[-2].blocks)
        if last_h < usable_height * 0.5 and prev_h + last_h <= usable_height * 1.05:
            cards[-2].blocks.extend(cards[-1].blocks)
            cards.pop()
    
    # 封面卡片
    cover = Card(card_type="cover", title=title)
    
    # 设置页码
    total = len(cards) + 1  # +1 for cover
    cover.page_num = 1
    cover.total_pages = total
    for i, card in enumerate(cards):
        card.page_num = i + 2
        card.total_pages = total
    
    return [cover] + cards


def _draw_gradient_bg(ctx, theme):
    """绘制渐变背景"""
    gradient = cairo.LinearGradient(0, 0, 0, HEIGHT)
    gradient.add_color_stop_rgb(0, *theme["bg_start"])
    gradient.add_color_stop_rgb(1, *theme["bg_end"])
    ctx.set_source(gradient)
    ctx.rectangle(0, 0, WIDTH, HEIGHT)
    ctx.fill()


def _draw_page_indicator(ctx, page, total, theme):
    """绘制页码指示器"""
    y = HEIGHT - 60
    dot_size = 8
    gap = 20
    total_w = total * dot_size + (total - 1) * gap
    start_x = (WIDTH - total_w) / 2
    
    for i in range(total):
        x = start_x + i * (dot_size + gap) + dot_size / 2
        ctx.arc(x, y, dot_size / 2, 0, 2 * math.pi)
        if i == page - 1:
            ctx.set_source_rgb(*theme["accent"])
        else:
            ctx.set_source_rgba(*theme["muted"], 0.4)
        ctx.fill()


def render_cover(card: Card, theme_name: str = DEFAULT_THEME) -> str:
    """渲染封面卡片"""
    theme = THEMES[theme_name]
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    
    _draw_gradient_bg(ctx, theme)
    
    # 标题
    layout = PangoCairo.create_layout(ctx)
    
    title = card.title
    title_len = len(title)
    if title_len <= 8:
        font_size = 80
    elif title_len <= 14:
        font_size = 68
    elif title_len <= 20:
        font_size = 58
    else:
        font_size = 48
    
    font = Pango.FontDescription.from_string(f"Noto Sans CJK SC Bold {font_size}")
    layout.set_font_description(font)
    layout.set_width(CONTENT_WIDTH * Pango.SCALE)
    layout.set_alignment(Pango.Alignment.CENTER)
    layout.set_wrap(Pango.WrapMode.CHAR)
    layout.set_line_spacing(1.4)
    layout.set_text(title, -1)
    
    _, lr = layout.get_pixel_extents()
    x = (WIDTH - lr.width) / 2 - lr.x
    y = (HEIGHT - lr.height) / 2 - lr.y - 40
    
    ctx.move_to(x, y)
    ctx.set_source_rgb(*theme["title_color"])
    PangoCairo.show_layout(ctx, layout)
    
    # 装饰线
    line_y = (HEIGHT + lr.height) / 2 + 20
    line_w = 200
    ctx.set_source_rgba(*theme["accent"], 0.6)
    ctx.set_line_width(3)
    ctx.move_to((WIDTH - line_w) / 2, line_y)
    ctx.line_to((WIDTH + line_w) / 2, line_y)
    ctx.stroke()
    
    # "左滑查看" 提示
    hint_layout = PangoCairo.create_layout(ctx)
    hint_font = Pango.FontDescription.from_string("Noto Sans CJK SC 24")
    hint_layout.set_font_description(hint_font)
    hint_layout.set_text("← 左滑查看详细内容", -1)
    _, hlr = hint_layout.get_pixel_extents()
    ctx.move_to((WIDTH - hlr.width) / 2 - hlr.x, line_y + 40)
    ctx.set_source_rgba(*theme["muted"], 0.7)
    PangoCairo.show_layout(ctx, hint_layout)
    
    # 页码
    _draw_page_indicator(ctx, card.page_num, card.total_pages, theme)
    
    return _save_surface(surface)


def render_content_card(card: Card, theme_name: str = DEFAULT_THEME) -> str:
    """渲染内容卡片"""
    theme = THEMES[theme_name]
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    
    _draw_gradient_bg(ctx, theme)
    
    layout = PangoCairo.create_layout(ctx)
    layout.set_wrap(Pango.WrapMode.CHAR)
    
    y = PADDING
    
    for block in card.blocks:
        if block.type == "heading":
            size = 42 if block.level <= 2 else 36
            font = Pango.FontDescription.from_string(f"Noto Sans CJK SC Bold {size}")
            layout.set_font_description(font)
            layout.set_width(CONTENT_WIDTH * Pango.SCALE)
            layout.set_text(block.text, -1)
            
            # heading 下划线装饰
            _, lr = layout.get_pixel_extents()
            
            ctx.move_to(PADDING, y)
            ctx.set_source_rgb(*theme["title_color"])
            PangoCairo.show_layout(ctx, layout)
            
            # 左侧色条
            ctx.set_source_rgb(*theme["accent"])
            ctx.rectangle(PADDING - 15, y + 4, 5, lr.height - 8)
            ctx.fill()
            
            y += lr.height + 25
        
        elif block.type == "text":
            font = Pango.FontDescription.from_string("Noto Sans CJK SC 32")
            layout.set_font_description(font)
            layout.set_width(CONTENT_WIDTH * Pango.SCALE)
            layout.set_line_spacing(1.6)
            layout.set_text(block.text, -1)
            _, lr = layout.get_pixel_extents()
            
            ctx.move_to(PADDING, y)
            ctx.set_source_rgb(*theme["text_color"])
            PangoCairo.show_layout(ctx, layout)
            y += lr.height + 16
        
        elif block.type == "bullet":
            # 圆点
            ctx.set_source_rgb(*theme["bullet"])
            ctx.arc(PADDING + 10, y + 20, 6, 0, 2 * math.pi)
            ctx.fill()
            
            font = Pango.FontDescription.from_string("Noto Sans CJK SC 30")
            layout.set_font_description(font)
            layout.set_width((CONTENT_WIDTH - 40) * Pango.SCALE)
            layout.set_line_spacing(1.5)
            layout.set_text(block.text, -1)
            _, lr = layout.get_pixel_extents()
            
            ctx.move_to(PADDING + 35, y)
            ctx.set_source_rgb(*theme["text_color"])
            PangoCairo.show_layout(ctx, layout)
            y += lr.height + 12
        
        elif block.type == "numbered":
            # 数字圆圈
            ctx.set_source_rgb(*theme["accent"])
            ctx.arc(PADDING + 18, y + 18, 18, 0, 2 * math.pi)
            ctx.fill()
            
            num_layout = PangoCairo.create_layout(ctx)
            num_font = Pango.FontDescription.from_string("Noto Sans CJK SC Bold 22")
            num_layout.set_font_description(num_font)
            num_layout.set_text(str(block.level), -1)
            _, nlr = num_layout.get_pixel_extents()
            ctx.move_to(PADDING + 18 - nlr.width / 2 - nlr.x, y + 18 - nlr.height / 2 - nlr.y)
            ctx.set_source_rgb(*theme["bg_start"])
            PangoCairo.show_layout(ctx, num_layout)
            
            font = Pango.FontDescription.from_string("Noto Sans CJK SC 30")
            layout.set_font_description(font)
            layout.set_width((CONTENT_WIDTH - 55) * Pango.SCALE)
            layout.set_line_spacing(1.5)
            layout.set_text(block.text, -1)
            _, lr = layout.get_pixel_extents()
            
            ctx.move_to(PADDING + 50, y)
            ctx.set_source_rgb(*theme["text_color"])
            PangoCairo.show_layout(ctx, layout)
            y += lr.height + 14
        
        elif block.type == "quote":
            # 引用条
            quote_h = 60  # 最小高度
            font = Pango.FontDescription.from_string("Noto Sans CJK SC 28")
            layout.set_font_description(font)
            layout.set_width((CONTENT_WIDTH - 80) * Pango.SCALE)
            layout.set_line_spacing(1.5)
            layout.set_text(block.text, -1)
            _, lr = layout.get_pixel_extents()
            quote_h = max(quote_h, lr.height + 30)
            
            # 背景
            ctx.set_source_rgba(*theme["card_bg"], 0.6)
            _rounded_rect(ctx, PADDING, y, CONTENT_WIDTH, quote_h, 12)
            ctx.fill()
            
            # 左边色条
            ctx.set_source_rgb(*theme["accent"])
            ctx.rectangle(PADDING, y, 5, quote_h)
            ctx.fill()
            
            ctx.move_to(PADDING + 30, y + 15)
            ctx.set_source_rgba(*theme["text_color"], 0.85)
            PangoCairo.show_layout(ctx, layout)
            y += quote_h + 16
        
        elif block.type == "code":
            font = Pango.FontDescription.from_string("Noto Sans Mono 24")
            layout.set_font_description(font)
            layout.set_width((CONTENT_WIDTH - 50) * Pango.SCALE)
            layout.set_text(block.text, -1)
            _, lr = layout.get_pixel_extents()
            code_h = lr.height + 40
            
            # 代码背景
            ctx.set_source_rgba(*theme["card_bg"], 0.8)
            _rounded_rect(ctx, PADDING, y, CONTENT_WIDTH, code_h, 12)
            ctx.fill()
            
            ctx.move_to(PADDING + 25, y + 20)
            ctx.set_source_rgba(*theme["text_color"], 0.9)
            PangoCairo.show_layout(ctx, layout)
            y += code_h + 16
        
        elif block.type == "tag":
            font = Pango.FontDescription.from_string("Noto Sans CJK SC 26")
            layout.set_font_description(font)
            layout.set_width(CONTENT_WIDTH * Pango.SCALE)
            layout.set_text(block.text, -1)
            _, lr = layout.get_pixel_extents()
            
            ctx.move_to(PADDING, y)
            ctx.set_source_rgba(*theme["accent"], 0.7)
            PangoCairo.show_layout(ctx, layout)
            y += lr.height + 10
    
    # 页码
    _draw_page_indicator(ctx, card.page_num, card.total_pages, theme)
    
    return _save_surface(surface)


def _rounded_rect(ctx, x, y, w, h, r):
    """绘制圆角矩形路径"""
    ctx.new_path()
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.arc(x + w - r, y + r, r, 3 * math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.close_path()


def _save_surface(surface) -> str:
    """保存 surface 为 JPG"""
    ts = int(time.time() * 1000)
    png_path = f"/tmp/xhs-card-{ts}.png"
    jpg_path = f"/tmp/xhs-card-{ts}.jpg"
    surface.write_to_png(png_path)
    
    try:
        from PIL import Image
        img = Image.open(png_path).convert("RGB")
        img.save(jpg_path, "JPEG", quality=92)
        os.remove(png_path)
        return jpg_path
    except Exception:
        return png_path


def content_to_cards(title: str, content: str, theme: str = DEFAULT_THEME) -> List[str]:
    """主入口：文章内容 → 多张卡片图路径

    Args:
        title: 文章标题
        content: 文章正文（可以是 markdown 格式）
        theme: 主题名 (tech/warm/fresh)

    Returns:
        图片路径列表
    """
    if theme not in THEMES:
        theme = DEFAULT_THEME
    
    blocks = parse_content(content)
    cards = split_into_cards(title, blocks, theme)
    
    paths = []
    for card in cards:
        if card.card_type == "cover":
            paths.append(render_cover(card, theme))
        else:
            paths.append(render_content_card(card, theme))
    
    return paths


# CLI 测试入口
if __name__ == "__main__":
    import sys
    
    test_content = """🌟 零基础也能学会AI编程！

### 1. 准备工具
1. 安装Python：官网下载最新版
2. 编辑器推荐Google Colab
3. 浏览器打开就能写代码

### 2. Python基础速通
不用学太深，先搞定**变量、列表、循环**就行。
B站搜"Python零基础教程"，宝藏视频超多！

### 3. AI入门实战
安装库：`pip install numpy pandas scikit-learn`

试试这些项目：
- 用sklearn做鸢尾花分类
- 调用OpenAI API写聊天机器人
- 做个简单情感分析工具

> 每天学一点，坚持就是胜利！

#AI编程入门 #Python编程 #科技女孩"""
    
    theme = sys.argv[1] if len(sys.argv) > 1 else "tech"
    paths = content_to_cards("AI编程入门指南🚀", test_content, theme)
    print(f"生成 {len(paths)} 张卡片:")
    for p in paths:
        print(f"  {p}")
