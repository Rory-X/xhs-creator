"""LLM 调用封装 - 通过子进程调用 grok.py"""

import json
import subprocess
import sys

from .config import load_config

GROK_TOOL_PATH = "/home/node/clawd/tools/grok.py"


def call_llm(query, system_prompt, model=None):
    """
    调用 LLM，通过子进程调用 grok.py

    Args:
        query: 用户查询内容
        system_prompt: 系统提示词
        model: 模型名称，默认从配置读取

    Returns:
        dict: {"content": str, "model": str, "usage": dict} 或 {"error": str}
    """
    cfg = load_config()

    if model is None:
        model = cfg["llm"]["model"]

    cmd = [
        sys.executable, GROK_TOOL_PATH,
        query,
        "-m", model,
        "--json",
    ]

    if system_prompt:
        # 在 system prompt 末尾追加反 think 标签指令
        system_prompt_final = (
            system_prompt.rstrip()
            + "\n\n不要输出任何推理过程，不要使用<think>标签，只返回纯JSON。"
        )
        cmd.extend(["-s", system_prompt_final])

    timeout = cfg["llm"].get("timeout", 300)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "未知错误"
            return {"error": f"LLM 调用失败: {error_msg}"}

        output = result.stdout.strip()
        if not output:
            return {"error": "LLM 返回为空"}

        data = json.loads(output)
        # 兜底清理 content 中的 <think> 标签
        if "content" in data and isinstance(data["content"], str):
            data["content"] = _strip_think_tags(data["content"]).strip()
        return data

    except subprocess.TimeoutExpired:
        return {"error": f"LLM 调用超时 ({timeout}秒)"}
    except json.JSONDecodeError as e:
        return {"error": f"解析 LLM 响应失败: {e}"}
    except Exception as e:
        return {"error": f"LLM 调用异常: {e}"}


def _strip_think_tags(text):
    """去掉 LLM 输出中的 <think>...</think> 标签及内容，清理残留换行"""
    import re
    # 去掉 <think>...</think> 块
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # 清理连续多个换行为单个换行
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def parse_llm_json(content):
    """从 LLM 返回的文本中解析 JSON

    使用括号匹配法提取 JSON，兼容 markdown 代码块和 <think> 标签。

    Returns:
        dict/list 或 None（解析失败时）
    """
    import re

    # 1. 先 strip think 标签
    text = _strip_think_tags(content).strip()

    # 2. 找到第一个 { 或 [
    start_idx = -1
    open_char = None
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            start_idx = i
            open_char = ch
            break

    if start_idx == -1:
        return None

    close_char = '}' if open_char == '{' else ']'

    # 3. 用括号匹配法找到对应的 } 或 ]
    depth = 0
    in_string = False
    escape = False
    end_idx = -1

    for i in range(start_idx, len(text)):
        ch = text[i]

        if escape:
            escape = False
            continue

        if ch == '\\' and in_string:
            escape = True
            continue

        if ch == '"' and not escape:
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                end_idx = i
                break

    if end_idx == -1:
        return None

    json_str = text[start_idx:end_idx + 1]

    # 4. 尝试 json.loads
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 5. 失败则尝试修复常见问题
    fixed = json_str

    # 修复字符串值内的裸换行
    fixed = re.sub(
        r'(?<=": ")((?:[^"\\]|\\.)*)(?=")',
        lambda m: m.group(0).replace('\n', ' ').replace('\r', ''),
        fixed,
    )

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 去除尾部逗号（如 ,} 或 ,]）
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 暴力修复：替换所有字符串值中的换行为空格
    fixed = re.sub(
        r'(?<=: ")[^"]*(?=")',
        lambda m: m.group(0).replace('\n', ' '),
        fixed,
    )
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 6. 最终失败返回 None
    return None
