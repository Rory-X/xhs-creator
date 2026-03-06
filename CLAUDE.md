# CLAUDE.md — xhs-creator 项目指南

## 项目概述
AI 驱动的小红书内容创作 CLI 工具，通过 LLM 生成小红书笔记内容并自动发布。

## 技术栈
- Python 3.8+, Click CLI, PyYAML, Pillow
- LLM: grok-4.20-beta (chat.tabcode.cc, OpenAI兼容)
- 小红书: 通过 MCP 服务 (localhost:18060) 交互
- 安装: `pip install -e .` → CLI 命令 `xhs-creator`

## 目录结构
```
xhs_creator/
├── cli.py          # Click group 入口
├── config.py       # 配置管理 (~/.xhs-creator/config.yaml)
├── llm.py          # LLM API 调用 (SSE streaming, think标签清理, JSON解析)
├── formatter.py    # 终端格式化输出 (Rich)
├── prompts.py      # 所有 LLM prompt 模板
├── xhs_client.py   # 小红书 MCP 客户端封装
└── commands/
    ├── topic.py    # 热点选题 (联网搜索)
    ├── title.py    # 标题生成 (5个候选)
    ├── write.py    # 正文写作 (含emoji/排版)
    ├── analyze.py  # 内容分析优化
    ├── publish.py  # 发布到小红书 (自动Pillow封面图)
    └── config_cmd.py # 配置管理
```

## 关键命令
```bash
xhs-creator topic "AI"        # 热点选题
xhs-creator title "主题"      # 生成标题
xhs-creator write "标题"      # 写正文
xhs-creator analyze "内容"    # 分析优化
xhs-creator publish -t "标题" -c "内容"  # 发布
xhs-creator config show/set/init
```

## 注意事项
- LLM 返回可能包含 `<think>` 标签，llm.py 会自动清理
- JSON 解析用括号匹配法（非正则），处理 markdown 包裹
- 封面图自动去除 emoji（Pillow 不支持彩色 emoji 渲染）
- 标题限制 20 字
- MCP 服务需要 Chrome 运行环境
- config.yaml 中 `image_gen.enabled: false`（Gemini token 用完了）

## 开发
```bash
pip install -e .           # 安装开发模式
xhs-creator config show    # 查看配置
```

## 相关文件
- MCP CLI: /home/node/clawd/tools/xhs.py
- MCP 二进制: /home/node/clawd/tools/xiaohongshu/xiaohongshu-mcp-linux-amd64
- 自动发帖: /home/node/clawd/scripts/auto-xhs-post.py
