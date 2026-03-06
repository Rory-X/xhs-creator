# 小红书内容创作工具 CLI (xhs-creator)

## 目标
一个命令行工具，帮助用户高效创作小红书内容。

## 核心功能
1. **选题生成** — 输入领域/关键词，AI 生成多个选题建议
2. **标题优化** — 生成符合小红书风格的标题（≤20字，含 emoji）
3. **正文撰写** — 根据选题自动生成正文（≤1000字，含话题标签）
4. **图文排版建议** — 推荐图片风格、封面文案
5. **竞品分析** — 搜索小红书同类内容，分析爆款特征
6. **一键发布** — 直接通过小红书 MCP 发布内容

## 技术栈
- Python 3 CLI（click/argparse）
- 调用 LLM API 做内容生成
- 调用小红书 MCP 做搜索和发布
- 本地配置文件管理账号和偏好

## 使用示例
```bash
xhs-creator topic "美食探店"        # 生成选题
xhs-creator title "探店记录"        # 优化标题  
xhs-creator write --topic "xxx"     # 撰写正文
xhs-creator analyze "关键词"        # 竞品分析
xhs-creator publish --title "xxx" --content "xxx" --images "a.jpg,b.jpg"  # 发布
```
