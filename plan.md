# xhs-creator 实施计划

## 1. 项目结构

```
xhs-creator/
├── README.md
├── requirements.md
├── plan.md
├── pyproject.toml              # 项目元数据 + 依赖 + entry_points
├── requirements.txt            # pip 依赖锁定
│
├── xhs_creator/                # 主包
│   ├── __init__.py             # 版本号
│   ├── cli.py                  # Click 入口，注册所有子命令
│   ├── config.py               # 配置管理（加载/保存/默认值）
│   ├── llm.py                  # LLM 调用封装（包装 grok.py）
│   ├── xhs.py                  # 小红书操作封装（包装 tools/xhs.py）
│   ├── prompts.py              # 所有 system_prompt 模板集中管理
│   ├── formatter.py            # 输出格式化（text/json 双模式）
│   │
│   └── commands/               # 子命令实现
│       ├── __init__.py
│       ├── topic.py            # topic 选题生成
│       ├── title.py            # title 标题优化
│       ├── write.py            # write 正文撰写
│       ├── analyze.py          # analyze 竞品分析
│       ├── publish.py          # publish 一键发布
│       └── config_cmd.py       # config 配置管理
│
└── tests/                      # 测试
    ├── __init__.py
    ├── conftest.py             # pytest fixtures（mock LLM/XHS）
    ├── test_config.py
    ├── test_prompts.py
    ├── test_formatter.py
    ├── test_topic.py
    ├── test_title.py
    ├── test_write.py
    ├── test_analyze.py
    └── test_publish.py
```

**配置文件运行时路径：** `~/.xhs-creator/config.yaml`
**历史记录路径：** `~/.xhs-creator/history/`

---

## 2. 技术选型

### CLI 框架：Click（而非 argparse）

| 维度 | Click | argparse |
|------|-------|----------|
| 子命令支持 | `@click.group()` 原生支持，声明式 | 需手动 `add_subparsers`，代码冗长 |
| 参数验证 | 内置类型/范围校验、`click.Choice` | 需自行编写 |
| 输出美化 | `click.echo`/`click.style` 直接支持彩色 | 需额外引入 |
| 可测试性 | 自带 `CliRunner` 做集成测试 | 需手动构造 |
| 嵌套子命令 | `config` 下的 `show/set/reset/init` 天然适配 | 需嵌套 subparsers |

**结论：** Click 更适合本项目多子命令 + 嵌套子命令的场景。

### 配置管理：PyYAML

- 配置文件格式：YAML（符合需求文档设计）
- 用 `PyYAML` 读写，无需额外抽象层
- 配置加载优先级：命令行参数 > 配置文件 > 默认值

### 依赖清单

```
click>=8.0
pyyaml>=6.0
```

仅两个外部依赖。LLM 和小红书操作通过直接 import 已有的 `tools/grok.py` 和 `tools/xhs.py`，不引入额外 HTTP 库。

---

## 3. 开发阶段

### Phase 1：基础框架 + 配置管理

**目标：** 搭建项目骨架，实现 `xhs-creator config` 命令，确保 CLI 能正常运行。

#### 任务清单

| # | 任务 | 产出文件 | 验收标准 |
|---|------|---------|---------|
| 1.1 | 创建项目结构和 `pyproject.toml` | `pyproject.toml`, 包目录 | `pip install -e .` 成功，`xhs-creator --help` 输出帮助 |
| 1.2 | 实现配置模块 `config.py` | `xhs_creator/config.py` | 能加载/保存/合并默认值，支持点号路径访问（如 `llm.model`） |
| 1.3 | 实现 CLI 入口 `cli.py` | `xhs_creator/cli.py` | `@click.group()` 注册，`--version` 能输出版本号 |
| 1.4 | 实现 `config` 子命令 | `xhs_creator/commands/config_cmd.py` | `config show` 显示配置；`config set llm.model xxx` 修改成功；`config reset` 恢复默认；`config init` 交互式引导 |
| 1.5 | 实现输出格式化模块 | `xhs_creator/formatter.py` | `format_text()` 带彩色输出，`format_json()` 结构化输出 |
| 1.6 | 编写 Phase 1 测试 | `tests/test_config.py` | 配置读写、默认值合并、点号路径全部通过 |

#### 实现要点

**config.py 核心逻辑：**
```python
CONFIG_DIR = Path.home() / ".xhs-creator"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "llm": {
        "api_url": "https://chat.tabcode.cc/v1/chat/completions",
        "api_key": "",
        "model": "grok-4.20-beta",
        "temperature": 0.7,
        "timeout": 300,
    },
    "xhs": {
        "mcp_port": 18060,
        "auto_start": True,
        "tools_path": "/home/node/clawd/tools/xhs.py",
    },
    "defaults": {
        "style": "种草",
        "tone": "活泼",
        "length": "medium",
        "emoji": True,
        "max_title_length": 20,
    },
    # ...
}

def load_config() -> dict     # 加载 yaml，与默认值深度合并
def save_config(cfg: dict)    # 写入 yaml
def get_value(key: str)       # 支持 "llm.model" 点号访问
def set_value(key: str, value)# 支持 "llm.model" 点号写入
def reset_config()            # 写入 DEFAULT_CONFIG
```

**pyproject.toml 入口：**
```toml
[project.scripts]
xhs-creator = "xhs_creator.cli:cli"
```

---

### Phase 2：核心命令 — topic / title / write

**目标：** 实现三个 LLM 驱动的内容生成命令。

#### 任务清单

| # | 任务 | 产出文件 | 验收标准 |
|---|------|---------|---------|
| 2.1 | 实现 LLM 调用封装 `llm.py` | `xhs_creator/llm.py` | 包装 `grok_search()`，读取 config 中的 api_url/model/temperature，返回结构化结果 |
| 2.2 | 编写 prompts 模板 `prompts.py` | `xhs_creator/prompts.py` | 包含 `TOPIC_SYSTEM_PROMPT`、`TITLE_SYSTEM_PROMPT`、`WRITE_SYSTEM_PROMPT`、`ANALYZE_SYSTEM_PROMPT`，每个 prompt 要求 LLM 返回可解析的 JSON |
| 2.3 | 实现 `topic` 命令 | `xhs_creator/commands/topic.py` | `xhs-creator topic "美食探店" -n 5` 输出选题列表；`--json` 输出 JSON；`--style` 指定风格 |
| 2.4 | 实现 `title` 命令 | `xhs_creator/commands/title.py` | `xhs-creator title "探店记录" -n 5` 输出标题；`--style` 支持悬念/数字/情感/对比 |
| 2.5 | 实现 `write` 命令 | `xhs_creator/commands/write.py` | `xhs-creator write -t "选题"` 输出正文+标签；`--length` 控制篇幅；`--image-tips` 输出图片建议 |
| 2.6 | 编写 Phase 2 测试 | `tests/test_topic.py` 等 | mock LLM 返回，验证参数传递、prompt 构造、输出格式化 |

#### 实现要点

**llm.py 封装：**
```python
import sys
sys.path.insert(0, "/home/node/clawd/tools")
from grok import grok_search

def call_llm(query: str, system_prompt: str) -> dict:
    """调用 LLM，从 config 读取参数，返回 {"content": str} 或 {"error": str}"""
    cfg = load_config()
    return grok_search(
        query=query,
        model=cfg["llm"]["model"],
        system_prompt=system_prompt,
    )
```

**prompts.py 设计原则：**
- 每个 prompt 明确要求 LLM 以 JSON 格式返回，便于解析
- prompt 中嵌入参数占位符（如 `{count}`、`{style}`），由命令层 `.format()` 填充
- JSON 输出模式下直接传递 LLM 返回；text 模式下由 `formatter.py` 美化

**topic prompt 示例：**
```python
TOPIC_SYSTEM_PROMPT = """你是小红书选题生成专家。
用户会提供一个领域或关键词，请生成 {count} 个选题建议。
风格偏好：{style}

{hot_context}

请严格按以下 JSON 格式返回：
{{
  "keyword": "用户输入的关键词",
  "topics": [
    {{
      "title": "选题标题",
      "angle": "创作角度",
      "heat_score": 1-5的整数,
      "tags": ["标签1", "标签2"]
    }}
  ]
}}
只返回 JSON，不要添加其他文字。"""
```

---

### Phase 3：搜索分析 — analyze

**目标：** 实现 `analyze` 命令，需要同时调用小红书搜索和 LLM 分析。

#### 任务清单

| # | 任务 | 产出文件 | 验收标准 |
|---|------|---------|---------|
| 3.1 | 实现小红书操作封装 `xhs.py` | `xhs_creator/xhs.py` | 包装 `tools/xhs.py` 的 search/detail/publish 功能，提供 Python API |
| 3.2 | 实现 `analyze` 命令 | `xhs_creator/commands/analyze.py` | `xhs-creator analyze "美食探店"` 输出分析报告；`--detail` 输出每条笔记摘要 |
| 3.3 | 为 `topic --hot` 添加搜索增强 | `xhs_creator/commands/topic.py` | `--hot` 先搜索热门笔记，将结果注入 prompt context |
| 3.4 | MCP 服务自动管理 | `xhs_creator/xhs.py` | 调用前自动检测 MCP 服务状态，未启动时根据 `xhs.auto_start` 配置自动拉起 |
| 3.5 | 编写 Phase 3 测试 | `tests/test_analyze.py` | mock xhs 搜索返回 + mock LLM 分析返回，验证完整流程 |

#### 实现要点

**xhs.py 封装（项目内部的）：**
```python
import sys
sys.path.insert(0, "/home/node/clawd/tools")
import xhs as xhs_tool

def ensure_mcp_running():
    """确保 MCP 服务运行中，必要时自动启动"""

def search_notes(keyword: str, limit: int = 10) -> list[dict]:
    """搜索笔记，返回结构化列表"""

def get_note_detail(feed_id: str, xsec_token: str) -> dict:
    """获取笔记详情"""

def publish_note(title: str, content: str, images: list[str] = None) -> dict:
    """发布笔记"""
```

**analyze 数据流：**
1. 调用 `search_notes()` 获取笔记列表
2. 如果 `--detail`，逐条调用 `get_note_detail()` 获取完整内容
3. 将搜索结果/详情组装为 context 字符串
4. 构造 `ANALYZE_SYSTEM_PROMPT`，调用 LLM 分析
5. 解析 LLM 返回的 JSON，格式化输出

---

### Phase 4：发布 — publish

**目标：** 实现 `publish` 命令，支持内容校验、预览确认、发布。

#### 任务清单

| # | 任务 | 产出文件 | 验收标准 |
|---|------|---------|---------|
| 4.1 | 实现 `publish` 命令 | `xhs_creator/commands/publish.py` | `xhs-creator publish -t "标题" -c "正文"` 发布成功；`--images` 支持图片 |
| 4.2 | 实现预览确认流程 | 同上 | 默认显示预览 + `[y/N]` 确认；`--no-confirm` 跳过 |
| 4.3 | 实现草稿模式 | 同上 | `--draft` 保存为草稿 |
| 4.4 | 内容校验 | 同上 | 标题 > 20 字报错；正文 > 1000 字报错；自动检测登录状态 |
| 4.5 | 编写 Phase 4 测试 | `tests/test_publish.py` | mock 发布 API，验证校验逻辑和确认流程 |

#### 实现要点

**publish 流程：**
```
1. 校验 title 长度 ≤ 20 字
2. 校验 content 长度 ≤ 1000 字
3. 检查图片路径是否存在（如有 --images）
4. 确保 MCP 服务运行
5. 检查登录状态
6. 显示发布预览（除非 --no-confirm）
7. 等待用户确认
8. 调用 publish_note() 发布
9. 输出结果
```

---

## 4. 测试策略

### 测试框架
- **pytest** + **click.testing.CliRunner**

### Mock 策略

所有测试均不依赖真实 API，通过 mock 隔离外部调用：

```python
# conftest.py
@pytest.fixture
def mock_llm(monkeypatch):
    """Mock LLM 调用，返回预设 JSON"""
    def fake_call(query, system_prompt):
        return {"content": '{"topics": [...]}', "model": "test", "usage": {}}
    monkeypatch.setattr("xhs_creator.llm.call_llm", fake_call)

@pytest.fixture
def mock_xhs(monkeypatch):
    """Mock 小红书操作"""
    monkeypatch.setattr("xhs_creator.xhs.search_notes", lambda **kw: [...])
    monkeypatch.setattr("xhs_creator.xhs.publish_note", lambda **kw: {"success": True})
```

### 测试覆盖范围

| 层 | 测试内容 | 方式 |
|----|---------|------|
| config | 加载/保存/默认值合并/点号路径/reset | 单元测试，用 `tmp_path` 隔离文件系统 |
| prompts | prompt 模板 format 不报错，占位符完整 | 单元测试 |
| formatter | text 输出格式正确，json 输出可解析 | 单元测试 |
| commands | 参数解析正确、prompt 传参正确、输出符合预期 | CliRunner 集成测试 + mock |
| 校验 | 标题超长、正文超长、缺少必填项 | CliRunner 测试异常路径 |

### 运行方式

```bash
# 全部测试
pytest tests/ -v

# 单个阶段
pytest tests/test_config.py -v          # Phase 1
pytest tests/test_topic.py tests/test_title.py tests/test_write.py -v  # Phase 2
pytest tests/test_analyze.py -v         # Phase 3
pytest tests/test_publish.py -v         # Phase 4
```

---

## 5. 执行顺序总结

```
Phase 1 (基础框架)     ← 先搭骨架，确保 CLI 能跑
  ↓
Phase 2 (内容生成)     ← 核心价值：topic/title/write
  ↓
Phase 3 (搜索分析)     ← 依赖 MCP 服务：analyze + topic --hot
  ↓
Phase 4 (发布)         ← 最后对接发布流程
```

每个 Phase 完成后运行该阶段测试，全部通过后再进入下一阶段。
