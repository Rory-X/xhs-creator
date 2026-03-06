"""md2xhs - Markdown 转小红书纯文本格式"""

import re


def md_to_xhs(text: str) -> str:
    """将 Markdown 格式文本转换为小红书友好的纯文本格式

    转换规则：
    - ### 标题 → 用 emoji 强调的段落标题（去掉 #）
    - **粗体** → 直接去掉 ** 标记
    - `代码` → 「代码」
    - ```代码块``` → 代码内容加缩进
    - [链接](url) → 链接文字
    - - 列表项 → ▪ 列表项
    - 1. 有序列表 → 保留数字 + emoji
    - > 引用 → 「引用内容」
    - --- 分割线 → ✦────────✦
    - 图片 ![alt](url) → 去掉
    """
    if not text:
        return text

    lines = text.split("\n")
    result = []
    in_code_block = False

    for line in lines:
        # 代码块
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                result.append("📝 代码示例 ↓")
            else:
                result.append("")  # 代码块结束空行
            continue

        if in_code_block:
            result.append(f"  {line}")
            continue

        # 空行保留
        if not line.strip():
            result.append("")
            continue

        # 分割线
        if re.match(r"^---+$", line.strip()):
            result.append("✦────────✦")
            continue

        # 图片 — 去掉
        if re.match(r"^!\[.*?\]\(.*?\)", line.strip()):
            continue

        # 标题 ### / ## / #
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            title_text = heading_match.group(2)
            # 清理标题中的 markdown 语法
            title_text = _inline_clean(title_text)
            # 不同级别用不同处理
            if level <= 2:
                result.append(f"\n{'━' * 20}")
                result.append(f"📌 {title_text}")
                result.append(f"{'━' * 20}")
            else:
                result.append(f"\n{title_text}")
            continue

        # 无序列表
        bullet_match = re.match(r"^[-*+]\s+(.*)", line)
        if bullet_match:
            item = _inline_clean(bullet_match.group(1))
            result.append(f"▪ {item}")
            continue

        # 有序列表
        ordered_match = re.match(r"^(\d+)[.)]\s+(.*)", line)
        if ordered_match:
            num = ordered_match.group(1)
            item = _inline_clean(ordered_match.group(2))
            # 数字 emoji 映射
            num_emoji = {
                "1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣", "5": "5️⃣",
                "6": "6️⃣", "7": "7️⃣", "8": "8️⃣", "9": "9️⃣", "10": "🔟",
            }
            prefix = num_emoji.get(num, f"{num}.")
            result.append(f"{prefix} {item}")
            continue

        # 引用
        quote_match = re.match(r"^>\s*(.*)", line)
        if quote_match:
            quote_text = _inline_clean(quote_match.group(1))
            result.append(f"「{quote_text}」")
            continue

        # 普通段落 — 清理内联 markdown
        result.append(_inline_clean(line))

    text = "\n".join(result)

    # 清理多余空行（最多保留两个连续换行）
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _inline_clean(text: str) -> str:
    """清理行内 markdown 语法"""
    # 粗斜体 ***text*** 或 ___text___
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"\1", text)
    # 粗体 **text** 或 __text__
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"\1", text)
    # 斜体 *text* 或 _text_（注意不匹配单词中的下划线）
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)
    # 行内代码
    text = re.sub(r"`(.+?)`", r"「\1」", text)
    # 链接 [text](url)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    # 删除线
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    # 清理转义的 markdown 字符
    text = text.replace("\\*", "*").replace("\\_", "_").replace("\\#", "#").replace("\\`", "`")
    return text
