"""小红书操作封装 - 通过子进程调用 tools/xhs.py"""

import json
import subprocess
import sys
import time

import click

from .config import load_config


def _get_xhs_tool_path():
    """获取 xhs.py 工具路径"""
    cfg = load_config()
    return cfg["xhs"]["tools_path"]


def _run_xhs_cmd(args, timeout=180):
    """运行 xhs.py 命令并返回解析后的结果

    Args:
        args: 命令参数列表，如 ["search", "-k", "美食"]
        timeout: 超时时间（秒）

    Returns:
        dict: 解析后的 JSON 结果或错误信息
    """
    tool_path = _get_xhs_tool_path()
    cmd = [sys.executable, tool_path, "--json"] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = result.stdout.strip()
        if not output:
            stderr = result.stderr.strip() if result.stderr else "无输出"
            return {"error": f"命令无输出: {stderr}"}

        return json.loads(output)

    except subprocess.TimeoutExpired:
        return {"error": f"命令超时 ({timeout}秒)"}
    except json.JSONDecodeError:
        return {"error": "解析响应失败", "raw": output}
    except Exception as e:
        return {"error": str(e)}


def ensure_mcp_running():
    """确保 MCP 服务运行中，必要时自动启动

    Returns:
        dict: {"ok": True} 或 {"error": str}
    """
    cfg = load_config()
    tool_path = cfg["xhs"]["tools_path"]

    # 尝试列出工具来检测服务是否运行
    test_result = _run_xhs_cmd(["tools"], timeout=10)

    if "error" in test_result and isinstance(test_result["error"], str):
        if cfg["xhs"].get("auto_start", True):
            click.echo("正在启动小红书 MCP 服务...")
            try:
                start_result = subprocess.run(
                    [sys.executable, tool_path, "start"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if start_result.returncode != 0:
                    stderr = start_result.stderr.strip() if start_result.stderr else "未知错误"
                    return {"error": f"MCP 服务启动失败: {stderr}"}
                time.sleep(3)
                click.echo("MCP 服务已启动")
                return {"ok": True}
            except subprocess.TimeoutExpired:
                return {"error": "MCP 服务启动超时"}
            except Exception as e:
                return {"error": f"MCP 服务启动异常: {e}"}
        else:
            return {"error": "MCP 服务未运行，请先执行: python3 /home/node/clawd/tools/xhs.py start"}

    return {"ok": True}


def search_notes(keyword, limit=10):
    """搜索小红书笔记

    Args:
        keyword: 搜索关键词
        limit: 结果数量

    Returns:
        dict: {"content": str, "raw": dict} 或 {"error": str}
    """
    args = ["search", "-k", keyword]
    # Note: MCP search_feeds does not support limit parameter

    result = _run_xhs_cmd(args)

    if "error" in result and isinstance(result["error"], str):
        return {"error": result["error"]}

    # 提取 MCP 响应中的文本内容
    content = result.get("result", {}).get("content", [])
    texts = []
    for item in content:
        if item.get("type") == "text":
            texts.append(item["text"])

    return {"content": "\n".join(texts), "raw": result}


def get_note_detail(feed_id, xsec_token):
    """获取笔记详情

    Args:
        feed_id: 笔记 ID
        xsec_token: xsec token

    Returns:
        dict: {"content": str, "raw": dict} 或 {"error": str}
    """
    result = _run_xhs_cmd(["detail", "--id", feed_id, "--token", xsec_token])

    if "error" in result and isinstance(result["error"], str):
        return {"error": result["error"]}

    content = result.get("result", {}).get("content", [])
    texts = []
    for item in content:
        if item.get("type") == "text":
            texts.append(item["text"])

    return {"content": "\n".join(texts), "raw": result}


def check_login():
    """检查小红书登录状态

    Returns:
        dict: {"content": str, "raw": dict} 或 {"error": str}
    """
    result = _run_xhs_cmd(["login"], timeout=30)

    if "error" in result and isinstance(result["error"], str):
        return {"error": result["error"]}

    content = result.get("result", {}).get("content", [])
    texts = []
    for item in content:
        if item.get("type") == "text":
            texts.append(item["text"])

    return {"content": "\n".join(texts), "raw": result}


def publish_note(title, content, images=None):
    """发布笔记

    Args:
        title: 笔记标题
        content: 笔记正文
        images: 图片路径列表

    Returns:
        dict: {"content": str, "raw": dict} 或 {"error": str}
    """
    args = ["publish", "-t", title, "-c", content]
    if images:
        args.extend(["-i", ",".join(images)])

    result = _run_xhs_cmd(args)

    if "error" in result and isinstance(result["error"], str):
        return {"error": result["error"]}

    content_list = result.get("result", {}).get("content", [])
    texts = []
    for item in content_list:
        if item.get("type") == "text":
            texts.append(item["text"])

    return {"content": "\n".join(texts), "raw": result}
