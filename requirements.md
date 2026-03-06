# xhs-creator 需求规格说明书

## 1. 用户画像

### 目标用户
- **小红书内容创作者**：个人博主、自媒体运营者，需要高效批量产出内容
- **品牌运营人员**：负责品牌小红书账号日常运营，需要快速生成符合平台调性的内容
- **新手创作者**：刚入驻小红书，不熟悉平台内容风格，需要 AI 辅助起步

### 使用场景
- 每日选题规划：快速获取所在领域的热门选题方向
- 标题优化：将普通标题改写为高点击率的小红书风格标题
- 正文生成：基于选题自动生成带话题标签的完整正文
- 竞品调研：搜索分析同领域爆款笔记的共性特征
- 内容发布：生成内容后一键发布，无需切换到小红书 App

### 用户技术水平
- 具备基本命令行操作能力
- 不需要编程经验，通过简单命令即可完成全部操作

---

## 2. 核心功能详细设计

### 2.1 `topic` — 选题生成

根据用户输入的领域或关键词，调用 LLM 生成多个选题建议。

**命令格式：**
```bash
xhs-creator topic <领域/关键词> [选项]
```

**参数与选项：**

| 参数/选项 | 类型 | 必填 | 默认值 | 说明 |
|-----------|------|------|--------|------|
| `keyword` | 位置参数 | 是 | — | 领域或关键词，如 "美食探店" |
| `-n, --count` | int | 否 | 5 | 生成选题数量 |
| `--style` | str | 否 | config 中的默认值 | 内容风格（种草/测评/教程/日常分享） |
| `--hot` | flag | 否 | false | 结合小红书热门趋势生成（调用 xhs.py 搜索） |
| `--json` | flag | 否 | false | 以 JSON 格式输出 |

**输出格式（默认）：**
```
🔥 "美食探店" 选题建议 (5条)

1. 【探店合集】本地人私藏的5家苍蝇馆子
   角度: 本地人视角 + 平价美食
   预估热度: ⭐⭐⭐⭐⭐

2. 【踩雷预警】网红餐厅真实测评
   角度: 反向测评 + 真实体验
   预估热度: ⭐⭐⭐⭐
...
```

**输出格式（JSON）：**
```json
{
  "keyword": "美食探店",
  "topics": [
    {
      "title": "本地人私藏的5家苍蝇馆子",
      "angle": "本地人视角 + 平价美食",
      "heat_score": 5,
      "tags": ["探店", "美食", "平价美食"]
    }
  ]
}
```

---

### 2.2 `title` — 标题优化

生成符合小红书风格的标题（≤20字，含 emoji，吸引点击）。

**命令格式：**
```bash
xhs-creator title <原始标题/主题> [选项]
```

**参数与选项：**

| 参数/选项 | 类型 | 必填 | 默认值 | 说明 |
|-----------|------|------|--------|------|
| `text` | 位置参数 | 是 | — | 原始标题或主题描述 |
| `-n, --count` | int | 否 | 5 | 生成标题数量 |
| `--style` | str | 否 | config 中的默认值 | 标题风格（悬念/数字/情感/对比） |
| `--emoji` | flag | 否 | true | 是否包含 emoji |
| `--max-len` | int | 否 | 20 | 标题最大字数 |
| `--json` | flag | 否 | false | 以 JSON 格式输出 |

**输出格式（默认）：**
```
✨ 标题优化建议 (基于: "探店记录")

1. 🍜 这家店排队2小时也值得！
2. 😱 人均30吃到撑的宝藏小店
3. 📍 本地人才知道的神仙馆子
4. 🔥 吃了100家选出的TOP1！
5. 💰 月薪3千也能天天下馆子
```

**输出格式（JSON）：**
```json
{
  "original": "探店记录",
  "titles": [
    {
      "text": "🍜 这家店排队2小时也值得！",
      "char_count": 13,
      "style": "悬念"
    }
  ]
}
```

---

### 2.3 `write` — 正文撰写

根据选题和参数自动生成小红书正文（≤1000字，含话题标签和排版建议）。

**命令格式：**
```bash
xhs-creator write --topic <选题> [选项]
```

**参数与选项：**

| 参数/选项 | 类型 | 必填 | 默认值 | 说明 |
|-----------|------|------|--------|------|
| `--topic, -t` | str | 是 | — | 选题内容或标题 |
| `--style` | str | 否 | config 中的默认值 | 写作风格（种草/测评/教程/日常分享/干货） |
| `--tone` | str | 否 | "活泼" | 语气（活泼/专业/亲切/搞笑） |
| `--length` | str | 否 | "medium" | 篇幅（short: ≤300字 / medium: 300-600字 / long: 600-1000字） |
| `--tags` | str | 否 | 自动生成 | 自定义话题标签，逗号分隔 |
| `--image-tips` | flag | 否 | false | 附带图片建议（封面文案、配图风格） |
| `--json` | flag | 否 | false | 以 JSON 格式输出 |

**输出格式（默认）：**
```
📝 正文生成完成

--- 正文 ---
姐妹们！！这家店我真的要吹爆 🔥

上周朋友带我去了一家隐藏在巷子里的小店...
（正文内容）

#美食探店 #平价美食 #本地探店 #必吃榜

--- 图片建议 ---
封面: 菜品特写 + 大字标题 "人均30的神仙小店"
图1: 店面外观（突出烟火气）
图2-4: 菜品近景（暖色调滤镜）
图5: 人均消费/菜单
```

**输出格式（JSON）：**
```json
{
  "topic": "探店记录",
  "content": "姐妹们！！这家店我真的要吹爆 🔥\n...",
  "char_count": 486,
  "tags": ["美食探店", "平价美食", "本地探店"],
  "image_tips": {
    "cover": "菜品特写 + 大字标题",
    "images": ["店面外观", "菜品近景", "人均消费"]
  }
}
```

---

### 2.4 `analyze` — 竞品分析

搜索小红书同类内容，分析爆款笔记特征，输出可借鉴的策略。

**命令格式：**
```bash
xhs-creator analyze <关键词> [选项]
```

**参数与选项：**

| 参数/选项 | 类型 | 必填 | 默认值 | 说明 |
|-----------|------|------|--------|------|
| `keyword` | 位置参数 | 是 | — | 搜索关键词 |
| `-n, --limit` | int | 否 | 10 | 分析笔记数量 |
| `--sort` | str | 否 | "hot" | 排序方式（hot: 热度 / new: 最新） |
| `--detail` | flag | 否 | false | 输出详细分析（含每条笔记摘要） |
| `--json` | flag | 否 | false | 以 JSON 格式输出 |

**输出格式（默认）：**
```
🔍 竞品分析: "美食探店" (共分析 10 篇笔记)

📊 爆款特征总结:
  标题规律: 80% 使用数字 + emoji，平均 15 字
  内容结构: 开头提问/感叹 → 分点推荐 → 总结互动
  常用标签: #探店 #美食推荐 #必吃 #吃货
  高频词汇: 姐妹们、绝绝子、人均、宝藏、踩雷
  配图风格: 暖色调、菜品特写为主
  互动数据: 平均点赞 1.2k, 收藏 800, 评论 200

💡 创作建议:
  1. 标题加入具体数字（如"5家""人均30"）
  2. 正文开头用感叹句引发共鸣
  3. 配图至少5张，首图突出核心卖点
```

**输出格式（JSON）：**
```json
{
  "keyword": "美食探店",
  "analyzed_count": 10,
  "summary": {
    "title_pattern": "80% 使用数字 + emoji",
    "avg_title_length": 15,
    "content_structure": "提问/感叹 → 分点推荐 → 总结互动",
    "top_tags": ["探店", "美食推荐", "必吃"],
    "top_keywords": ["姐妹们", "绝绝子", "宝藏"],
    "avg_likes": 1200,
    "avg_collects": 800,
    "avg_comments": 200
  },
  "suggestions": ["标题加入具体数字", "正文开头用感叹句", "配图至少5张"]
}
```

---

### 2.5 `publish` — 一键发布

将生成的内容直接发布到小红书。

**命令格式：**
```bash
xhs-creator publish --title <标题> --content <内容> [选项]
```

**参数与选项：**

| 参数/选项 | 类型 | 必填 | 默认值 | 说明 |
|-----------|------|------|--------|------|
| `--title, -t` | str | 是 | — | 笔记标题（≤20字） |
| `--content, -c` | str | 是 | — | 笔记正文（≤1000字） |
| `--images, -i` | str | 否 | — | 图片路径，逗号分隔 |
| `--draft` | flag | 否 | false | 保存为草稿而非直接发布 |
| `--confirm` | flag | 否 | true | 发布前显示预览并确认 |
| `--json` | flag | 否 | false | 以 JSON 格式输出 |

**输出格式（默认）：**
```
📤 发布预览:
  标题: 🍜 这家店排队2小时也值得！
  正文: (486字) 姐妹们！！这家店我真的要吹爆...
  图片: 3张 (a.jpg, b.jpg, c.jpg)

确认发布？[y/N] y

✅ 发布成功！
```

---

### 2.6 `config` — 配置管理

管理本地配置文件（API 设置、默认风格、领域偏好等）。

**命令格式：**
```bash
xhs-creator config <子命令> [选项]
```

**子命令：**

| 子命令 | 说明 | 示例 |
|--------|------|------|
| `show` | 显示当前配置 | `xhs-creator config show` |
| `set <key> <value>` | 设置配置项 | `xhs-creator config set style 种草` |
| `reset` | 恢复默认配置 | `xhs-creator config reset` |
| `init` | 交互式初始化配置 | `xhs-creator config init` |

**参数与选项：**

| 参数/选项 | 类型 | 必填 | 说明 |
|-----------|------|------|------|
| `subcommand` | 位置参数 | 是 | 子命令（show/set/reset/init） |
| `key` | 位置参数 | set 时必填 | 配置项键名（支持点号分隔，如 `llm.model`） |
| `value` | 位置参数 | set 时必填 | 配置项值 |
| `--json` | flag | 否 | 以 JSON 格式输出（仅 show） |

**输出格式（config show）：**
```
⚙️  当前配置 (~/.xhs-creator/config.yaml)

LLM:
  api_url:  https://chat.tabcode.cc/v1/chat/completions
  model:    grok-4.20-beta

默认风格:  种草
默认语气:  活泼
默认篇幅:  medium
领域偏好:  美食, 穿搭

小红书 MCP:
  端口: 18060
  状态: 运行中
```

---

## 3. 数据流设计

### 3.1 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                        用户 (CLI)                            │
│  topic / title / write / analyze / publish / config          │
└─────────────┬────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│                    xhs-creator (主程序)                       │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ │
│  │ 命令解析层   │→│  业务逻辑层  │→│   输出格式化层         │ │
│  │ (click)     │  │             │  │ (text/json)          │ │
│  └─────────────┘  └──────┬──────┘  └──────────────────────┘ │
│                          │                                   │
│              ┌───────────┴───────────┐                       │
│              ▼                       ▼                       │
│  ┌──────────────────┐   ┌──────────────────┐                 │
│  │  LLM 调用模块     │   │  小红书操作模块   │                 │
│  │  (grok_client)   │   │  (xhs_client)    │                 │
│  └────────┬─────────┘   └────────┬─────────┘                 │
│           │                      │                           │
│  ┌────────┴─────────┐   ┌───────┴──────────┐                │
│  │ 配置管理模块      │   │  配置管理模块     │                │
│  │ (config.yaml)    │   │  (config.yaml)   │                │
│  └──────────────────┘   └──────────────────┘                │
└──────────────────────────────────────────────────────────────┘
              │                       │
              ▼                       ▼
┌─────────────────────┐  ┌─────────────────────────┐
│  /home/node/clawd/  │  │  /home/node/clawd/      │
│  tools/grok.py      │  │  tools/xhs.py           │
│  (LLM API)         │  │  (小红书 MCP)            │
└─────────┬───────────┘  └─────────┬───────────────┘
          │                        │
          ▼                        ▼
┌─────────────────────┐  ┌─────────────────────────┐
│  Grok LLM API       │  │  小红书 MCP Server       │
│  (远程服务)          │  │  (本地 localhost:18060)  │
└─────────────────────┘  └─────────────────────────┘
```

### 3.2 各命令数据流

#### `topic` 选题生成
```
用户输入关键词
  → [可选] 调用 xhs.py search 获取热门笔记数据 (--hot 模式)
  → 构造 system_prompt (选题生成专用提示词)
  → 调用 grok.py 生成选题列表
  → 解析 LLM 返回 → 格式化输出
```

#### `title` 标题优化
```
用户输入原始标题
  → 构造 system_prompt (标题优化提示词，含小红书标题规则)
  → 调用 grok.py 生成标题
  → 解析 LLM 返回 → 格式化输出
```

#### `write` 正文撰写
```
用户输入选题 + 风格参数
  → 构造 system_prompt (正文撰写提示词，含风格/语气/篇幅约束)
  → 调用 grok.py 生成正文
  → 解析 LLM 返回 → 自动生成话题标签
  → [可选] 生成图片建议 (--image-tips)
  → 格式化输出
```

#### `analyze` 竞品分析
```
用户输入关键词
  → 调用 xhs.py search 搜索小红书笔记
  → [可选] 调用 xhs.py detail 获取每条笔记详情 (--detail)
  → 将搜索结果传给 grok.py，构造分析提示词
  → 调用 grok.py 进行特征总结与策略建议
  → 解析 LLM 返回 → 格式化输出
```

#### `publish` 一键发布
```
用户输入标题 + 正文 + 图片
  → 校验内容 (标题≤20字, 正文≤1000字)
  → [默认] 显示预览，等待用户确认
  → 调用 xhs.py publish 发布内容
  → 返回发布结果
```

#### `config` 配置管理
```
用户执行子命令
  → show: 读取 config.yaml → 格式化显示
  → set:  修改 config.yaml 中指定字段 → 保存
  → reset: 恢复默认 config.yaml
  → init: 交互式引导 → 生成 config.yaml
```

---

## 4. 外部依赖说明

### 4.1 LLM 调用 — `/home/node/clawd/tools/grok.py`

用于所有内容生成任务（选题、标题、正文、分析总结）。

**接口方式：** Python 模块导入或命令行调用

**模块调用方式：**
```python
from grok import grok_search

result = grok_search(
    query="用户问题",
    model="grok-4.20-beta",        # 可选，默认 grok-4.20-beta
    system_prompt="自定义提示词"     # 可选，用于定制生成行为
)
# result = {"content": "...", "model": "...", "usage": {...}}
# 或 {"error": "..."}
```

**命令行调用方式：**
```bash
python3 /home/node/clawd/tools/grok.py "查询内容" -s "系统提示词" --json
```

**关键特性：**
- API 端点：`https://chat.tabcode.cc/v1/chat/completions`（OpenAI 兼容接口）
- 默认模型：`grok-4.20-beta`
- 支持 SSE 流式响应和标准 JSON 响应
- 返回 token 用量统计（prompt_tokens / completion_tokens / total_tokens）
- 超时时间：300 秒

**在 xhs-creator 中的使用场景：**

| 命令 | system_prompt 要点 |
|------|-------------------|
| `topic` | 小红书选题生成专家，输出结构化选题列表 |
| `title` | 小红书标题优化专家，≤20字、含 emoji、制造悬念 |
| `write` | 小红书内容创作者，控制风格/语气/字数，自动插入话题标签 |
| `analyze` | 内容分析专家，基于搜索结果提取爆款规律和创作建议 |

---

### 4.2 小红书操作 — `/home/node/clawd/tools/xhs.py`

用于小红书平台交互（搜索、获取详情、发布内容）。

**接口方式：** Python 模块导入或命令行调用

**底层协议：** Streamable HTTP MCP（JSON-RPC 2.0），本地服务 `localhost:18060`

**可用 MCP 工具：**

| MCP 工具名 | 对应命令 | 说明 |
|------------|---------|------|
| `search_feeds` | `xhs.py search` | 搜索笔记，参数：keyword, limit |
| `list_feeds` | `xhs.py feed` | 获取推荐列表 |
| `get_feed_detail` | `xhs.py detail` | 获取笔记详情，参数：feed_id, xsec_token |
| `check_login_status` | `xhs.py login` | 检查登录状态 |
| `publish_content` | `xhs.py publish` | 发布图文，参数：title, content, images |

**命令行调用方式：**
```bash
# 前置：确保 MCP 服务已启动
python3 /home/node/clawd/tools/xhs.py start

# 搜索
python3 /home/node/clawd/tools/xhs.py search -k "美食探店" -n 10 --json

# 获取详情
python3 /home/node/clawd/tools/xhs.py detail --id <feed_id> --token <xsec_token> --json

# 发布
python3 /home/node/clawd/tools/xhs.py publish -t "标题" -c "正文" -i "a.jpg,b.jpg"
```

**在 xhs-creator 中的使用场景：**

| 命令 | 调用的 xhs.py 功能 |
|------|-------------------|
| `topic --hot` | `search` — 获取热门笔记辅助选题 |
| `analyze` | `search` + `detail` — 搜索并分析竞品笔记 |
| `publish` | `publish` — 发布生成的内容 |

**注意事项：**
- 使用前需确保 MCP 服务已启动（`xhs.py start`）
- 发布功能需要有效的小红书登录状态（`xhs.py login` 检查）
- xhs-creator 应在启动时自动检测 MCP 服务状态，未启动时自动拉起

---

## 5. 配置文件设计

### 文件路径
```
~/.xhs-creator/config.yaml
```

### 完整格式

```yaml
# xhs-creator 配置文件
# 通过 `xhs-creator config init` 交互式生成
# 通过 `xhs-creator config set <key> <value>` 修改

# ── LLM API 配置 ──
llm:
  api_url: "https://chat.tabcode.cc/v1/chat/completions"
  api_key: "sk-xxxxx"
  model: "grok-4.20-beta"
  temperature: 0.7            # 生成创造性，0-1，越高越有创意
  timeout: 300                # API 超时时间（秒）

# ── 小红书 MCP 配置 ──
xhs:
  mcp_port: 18060             # MCP 服务端口
  auto_start: true            # 执行命令时自动启动 MCP 服务
  tools_path: "/home/node/clawd/tools/xhs.py"

# ── 默认内容风格 ──
defaults:
  style: "种草"               # 默认写作风格: 种草 / 测评 / 教程 / 日常分享 / 干货
  tone: "活泼"                # 默认语气: 活泼 / 专业 / 亲切 / 搞笑
  length: "medium"            # 默认篇幅: short(≤300字) / medium(300-600字) / long(600-1000字)
  emoji: true                 # 标题和正文是否默认包含 emoji
  max_title_length: 20        # 标题最大字数

# ── 领域偏好 ──
domains:
  primary: "美食"              # 主要创作领域
  secondary:                   # 其他关注领域
    - "穿搭"
    - "旅行"
  custom_tags:                 # 常用自定义话题标签
    - "探店日记"
    - "好物分享"

# ── 输出设置 ──
output:
  format: "text"              # 默认输出格式: text / json
  color: true                 # 终端彩色输出
  save_history: true          # 保存生成历史
  history_dir: "~/.xhs-creator/history"
```

### 配置项说明

| 配置路径 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `llm.api_url` | str | `https://chat.tabcode.cc/v1/chat/completions` | LLM API 端点 |
| `llm.api_key` | str | — | API 密钥（首次使用需配置） |
| `llm.model` | str | `grok-4.20-beta` | 使用的模型 |
| `llm.temperature` | float | 0.7 | 生成温度 |
| `llm.timeout` | int | 300 | 请求超时（秒） |
| `xhs.mcp_port` | int | 18060 | MCP 服务端口 |
| `xhs.auto_start` | bool | true | 是否自动启动 MCP |
| `xhs.tools_path` | str | `/home/node/clawd/tools/xhs.py` | xhs.py 路径 |
| `defaults.style` | str | `种草` | 默认风格 |
| `defaults.tone` | str | `活泼` | 默认语气 |
| `defaults.length` | str | `medium` | 默认篇幅 |
| `defaults.emoji` | bool | true | 是否含 emoji |
| `defaults.max_title_length` | int | 20 | 标题字数上限 |
| `domains.primary` | str | — | 主要领域 |
| `domains.secondary` | list[str] | [] | 关注领域列表 |
| `domains.custom_tags` | list[str] | [] | 自定义标签 |
| `output.format` | str | `text` | 默认输出格式 |
| `output.color` | bool | true | 彩色输出 |
| `output.save_history` | bool | true | 保存历史 |
| `output.history_dir` | str | `~/.xhs-creator/history` | 历史记录目录 |
