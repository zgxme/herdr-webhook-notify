# herdr-webhook-notify

[![CI](https://github.com/zgxme/herdr-webhook-notify/actions/workflows/ci.yml/badge.svg)](https://github.com/zgxme/herdr-webhook-notify/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml) [![Herdr plugin](https://img.shields.io/badge/Herdr-plugin-6E56CF.svg)](https://herdr.dev/plugins/) [![Providers](https://img.shields.io/badge/providers-11-2EB67D.svg)](#支持的服务商)

把 [Herdr](https://herdr.dev) 的 agent 通知转发到你已经在用的渠道：飞书、钉钉、
Lark、企业微信、Slack、Discord、Microsoft Teams、Google Chat、Telegram、ntfy，
或者任意自定义 HTTP 接口。

[English](README.md) | [服务商配置指南](docs/providers.md) | [参与贡献](CONTRIBUTING.md)

```
herdr plugin install zgxme/herdr-webhook-notify
herdr plugin action invoke herdr-webhook-notify.init
herdr plugin action invoke herdr-webhook-notify.test
```

## 为什么需要它

Herdr 自带的应用内提示只在 Herdr 里可见。这个插件负责把通知推到你真正看得到的地方：
手机、团队群、或者自建的告警网关。

同时它解决了两个"自己写 hook 会踩"的坑：

- **正在看这个 pane 时完成会漏报**。Herdr 只在完成"未被查看"时报 `done`；当你正盯着
  那个 pane，同一个事件会以 `idle` 到达，只匹配 `done` 的 hook 会静默丢弃。插件按 pane
  记住上一个状态，把 `working|blocked -> idle` 也判定为一次完成。
- **事件里没有任务信息**。插件通过 Herdr CLI 回查 pane，补上任务概括（agent 的终端
  标题）、工作区、Tab、目录和 git 分支。

## 依赖

- Herdr 0.9.0 及以上
- Python 3.9 及以上（`python3` 在 `PATH` 上）。不需要 pip 安装任何依赖：Python 3.9 /
  3.10 会自动使用内置的 tomli 副本解析 TOML。

## 安装

```bash
herdr plugin install zgxme/herdr-webhook-notify
herdr plugin config-dir herdr-webhook-notify     # 打印配置目录
herdr plugin action invoke herdr-webhook-notify.init
```

`init` 会写出一份带注释、包含全部 provider 的 `config.toml`。启用其中一个并填入密钥：

```toml
[providers.feishu]
enabled = true
webhook_url = "${FEISHU_WEBHOOK}"
```

```dotenv
# 同目录下的 .env
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/...
```

```bash
herdr plugin action invoke herdr-webhook-notify.test
herdr plugin action invoke herdr-webhook-notify.status
```

本地开发时：

```bash
git clone https://github.com/zgxme/herdr-webhook-notify
herdr plugin link ./herdr-webhook-notify
```

## 触发范围

| 场景 | 事件状态 | 类型 | 默认 |
| --- | --- | --- | --- |
| 你在别的 tab / 切走时任务完成 | `done` | `done` | 通知 |
| 你正盯着该 pane 时任务完成 | `idle` | `done` | 通知 |
| 需要审批或提问 | `blocked` | `blocked` | 通知 |
| 中途状态无法判定 | `unknown` | `unknown` | 通知 |
| agent 进程退出或 pane 被关闭 | `pane.exited` / `pane.closed` | `exited` | 通知 |
| 开始干活 | `working` | - | 忽略 |
| 启动时空闲 | `idle` | - | 忽略 |

Herdr 没有显式的"失败"状态，`unknown` 和 `exited` 是最接近的两个信号，默认都会通知。

每个 hook 拿到的事件字段、以及插件如何把它变成通知，见
[docs/events.md](docs/events.md)。

## 配置

配置文件位于 `herdr plugin config-dir herdr-webhook-notify` 打印的目录中。密钥可以放在
同目录的 `.env` 里，用 `${NAME}` 引用；已经存在于进程环境中的变量优先，方便配合 CI 和
密钥管理。

### 配置从哪来

`config.toml` 的查找顺序：

1. `HERDR_WEBHOOK_NOTIFY_CONFIG`：直接指定文件路径。
2. `HERDR_PLUGIN_CONFIG_DIR` + `/config.toml`：插件配置目录。
3. 插件目录下的 `config.toml`。

`.env` 先读 `HERDR_PLUGIN_CONFIG_DIR`，再读插件目录。`HERDR_PLUGIN_STATE_DIR` 决定
`state.json` 的位置 —— Herdr 会把它设成 `~/.local/state/herdr/plugins/<plugin-id>`，
以 hook 方式运行时 cooldown 时间戳、耗时起点、失败重投队列都写在那里。
`HERDR_BIN_PATH` 决定插件用哪个 Herdr 二进制去补 pane、工作区和 tab 的名字。

两个列表语义容易踩坑：

- `notify.events = []` 不等于"不通知"：空列表会回落到四种类型全开。想去掉某类，就从
  列表里删掉它。
- `providers.<名字>.events = []` 同理，表示"该 provider 不做过滤"，而不是"永不通知"。

```toml
language = "zh-CN"                   # en | zh-CN

[notify]
events = ["done", "blocked", "unknown", "exited"]
notify_when_focused = true           # false = 只看后台 pane，盯着看时不打扰
min_turn_seconds = 0                 # 太短的 turn 不通知
cooldown_seconds = 5                 # 同一 pane 同类型去重
blocked_delay_seconds = 10           # 先等 auto approve，别误报
quiet_hours = ["22:00-08:00"]        # 本地时间，支持跨天
quiet_hours_exempt = ["blocked"]     # 免打扰期间例外
include_workspaces = []              # 支持 * 通配，大小写不敏感
exclude_workspaces = []
include_agents = []
exclude_agents = []

[message]
title = "Herdr {status_label}：{task}"
body = """
**状态**：{status_label}
**工作区**：{workspace}
**任务**：{task}
"""

[messages]
"status.done" = "搞定了"

[providers.slack]
enabled = true
webhook_url = "${SLACK_WEBHOOK}"
language = "en"                      # 可单独覆盖语言
events = ["blocked"]                 # 可单独覆盖事件范围
```

### 顶层配置

| 配置项 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `language` | 字符串 | `"en"` | 内置文案语言，可选 `en` 或 `zh-CN`；单个 provider 可以再覆盖。填错会直接报错，不会静默回退。 |

### `[notify]` 通知范围

| 配置项 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `events` | 列表 | `["done", "blocked", "unknown", "exited"]` | 允许通知的类型。`done` 同时覆盖"后台完成"和"你正盯着时完成"两种情况。 |
| `notify_when_focused` | 布尔 | `true` | `true` 表示你正看着那个 pane 完成时也通知；`false` 则跟 Herdr 原生行为一致，只看后台。 |
| `min_turn_seconds` | 数字 | `0` | 短于该秒数的 turn 不通知，`0` 表示不限制；只对 `done`/`blocked`/`unknown` 生效。 |
| `cooldown_seconds` | 数字 | `5` | 同一 pane 同一类型的通知在该时间窗内去重，可以把同一个 pane 重复的 `done` 合并成一条。不同类型分别计时，所以"完成 + pane 退出"（`done` + `exited`）仍然是两条；`0` 表示不去重。 |
| `blocked_delay_seconds` | 数字 | `10` | `blocked` 先等这么久再通知：等待结束后会重新查一次状态，agent 已经自己放行并继续执行就不发，避免 auto approve 造成的误报；`0` 表示立即通知。 |
| `quiet_hours` | 列表 | `[]` | 本地时间的免打扰区间，如 `["22:00-08:00"]`，支持跨天。 |
| `quiet_hours_exempt` | 列表 | `["blocked"]` | 免打扰期间仍然通知的类型，默认让审批/提问能吵醒你。 |
| `include_workspaces` | 通配列表 | `[]` | 只通知匹配的工作区名，如 `["external-*"]`；空表示全部。 |
| `exclude_workspaces` | 通配列表 | `[]` | 这些工作区永不通知；排除优先于包含。 |
| `include_tabs` / `exclude_tabs` | 通配列表 | `[]` | 同上，匹配 tab 的标签或编号。 |
| `include_agents` / `exclude_agents` | 通配列表 | `[]` | 同上，匹配 agent 类型（`codex`、`claude`、`gemini` 等）。 |

通配匹配大小写不敏感，支持 `*` 和 `?`。

### `[http]` 投递参数

| 配置项 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `timeout_seconds` | 数字 | `5` | 单次请求超时，最小 `0.1`。 |
| `retries` | 整数 | `1` | 网络错误和 `408/425/429/5xx` 的额外重试次数，`0` 表示只发一次。 |

### `[message]` 与 `[messages]` 文案

| 配置项 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `message.title` | 字符串 | 按语言内置 | 通知标题模板。 |
| `message.body` | 字符串 | 按语言内置 | 消息正文模板，可以用 TOML 多行字符串。 |
| `messages."status.done"` | 字符串 | 内置 | 覆盖单条内置文案。可用键：`status.done`、`status.blocked`、`status.unknown`、`status.exited`、`status.test`、`title`、`body`。因为含点号，TOML 里必须加引号。 |

### `[providers.<名字>]` 服务商

所有服务商都支持这三个键：

| 配置项 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `enabled` | 布尔 | `false` | 是否启用；未启用的 provider 不会做参数校验。 |
| `events` | 列表 | 继承全局 | 单独收窄范围，例如 Slack 只收 `["blocked"]`。 |
| `language` | 字符串 | 继承全局 | 单独指定语言，适合团队里中英混用的场景。 |
| `timeout_seconds` | 数字 | 继承 `[http]` | 单独设置超时，适合内部网关较慢的情况。 |
| `retries` | 数字 | 继承 `[http]` | 单独设置重试次数。 |

| 服务商 | 必填 | 可选 |
| --- | --- | --- |
| `feishu` | `webhook_url` | `secret`（签名）、`format`（`card`/`text`，默认 `card`）、`card_title_prefix` |
| `lark` | `webhook_url` | 同 `feishu` |
| `dingtalk` | `webhook_url` | `secret`（加签） |
| `wecom` | `key` 或 `webhook_url` | `base_url` |
| `slack` | `webhook_url` | - |
| `discord` | `webhook_url` | `username`、`avatar_url`、`content`（用于 @ 提醒） |
| `teams` | `webhook_url` | - |
| `google_chat` | `webhook_url` | `thread_key` |
| `telegram` | `bot_token`、`chat_id` | `parse_mode`（`HTML`/`MarkdownV2`）、`message_thread_id`、`disable_notification`、`api_base` |
| `ntfy` | `topic` | `url`、`token`、`priority`、`tags`、`click` |
| `generic` | `url` | `method`（`POST`/`PUT`/`PATCH`）、`headers`、`body`（模板）、`content_type`、`flavor`（`markdown`/`slack`/`plain`） |

各服务商怎么申请 webhook 见 [docs/providers.md](docs/providers.md)。

### 可用占位符

在 `message.title`、`message.body` 以及 `generic` 的 `body` 模板里都可以用：

| 占位符 | 含义 |
| --- | --- |
| `{status}` | 事件里 Herdr 的原始状态：`done`、`idle`、`blocked`、`unknown`、`exited`。你正盯着看时完成，这里会是 `idle`。 |
| `{status_label}` | 该类型本地化后的文案，例如 `任务完成`。 |
| `{kind}` | 归一化后的类型：`done`、`blocked`、`unknown`、`exited`、`test`。 |
| `{session}` | Herdr 会话名，默认会话显示 `default`。 |
| `{workspace}` | 工作区名称，例如 `external-fuzzer`；取不到时退回 workspace id。 |
| `{workspace_id}` | 工作区 id，例如 `wD`。 |
| `{tab}` | Tab 的标签或编号，例如 `2`。 |
| `{tab_id}` | Tab id，例如 `wD:t2`。 |
| `{task}` | 任务概括：pane 的终端标题，agent 会把会话标题写在这里；取不到时退回 pane id。 |
| `{agent}` | 检测到的 agent 类型，例如 `codex`、`claude`、`gemini`。 |
| `{pane_id}` | Pane id，例如 `wD:p1`。 |
| `{cwd}` | 该 pane 的工作目录。 |
| `{branch}` | `{cwd}` 所在的 git 分支，不在仓库里时为空。 |
| `{repo}` | 工作区所属 worktree 的仓库名；非 worktree 工作区为空。 |
| `{worktree}` | 工作区 worktree 的 checkout 路径；非 worktree 工作区为空。 |
| `{duration}` | 本轮耗时，格式化后如 `2m05s`。从 pane 进入 `working` 那一刻起算，等待审批的时间不计入；未知时为空。 |
| `{duration_seconds}` | 同样的耗时，纯秒数，方便自己格式化。 |
| `{host}` | 运行 Herdr 的机器名。 |
| `{time}` | 本地时间，格式 `YYYY-MM-DD HH:MM:SS`。 |

未知占位符会原样保留，写错能立刻看出来；整行只有空值的会被自动删掉，所以像 `{branch}`
这种可选字段不会留下空标签。耗时取不到时同理，`min_turn_seconds` 也会跳过比较。

## 支持的服务商

`feishu`、`lark`、`dingtalk`、`wecom`、`slack`、`discord`、`teams`、`google_chat`、
`telegram`、`ntfy`、`generic`。每个服务商的申请步骤和专属参数见
[docs/providers.md](docs/providers.md)。

## 命令（Actions）

| action | 作用 |
| --- | --- |
| `herdr-webhook-notify.init` | 写出带注释的 `config.toml` |
| `herdr-webhook-notify.test` | 给所有启用的 provider 发一条测试消息；`python3 run.py test [provider] [kind]` 可只测某一个、某一种类型 |
| `herdr-webhook-notify.preview` | 打印每个 provider 将要发送的请求，但不真的发送 |
| `herdr-webhook-notify.status` | 显示配置路径、provider、过滤规则和待重投队列 |
| `herdr-webhook-notify.mute` / `.resume` | 不改配置临时静音 / 恢复 |

## 可靠性

- hook 不会阻塞 Herdr：短超时、退出码 0、错误只写 stderr。
- 408/425/429/5xx 会做有限重试。
- 仍失败的通知会落到插件状态目录，下一次事件时重投，最多三次。
- 日志和 `status` 输出会隐藏 webhook URL 中的密钥片段。
- 配置里写错的键不会被静默忽略：`status` 和 hook 日志会提示 `unknown config key` 并给出拼写建议。

查看实际执行记录：

```bash
herdr plugin log list --plugin herdr-webhook-notify
```

## 开发

```bash
python3 -m pytest -q      # 70 个用例，不需要外网
python3 -m ruff check .
```

## 许可证

[MIT](LICENSE)。内置的 tomli 副本保留其自身的 MIT 许可证，见
`vendor/tomli/LICENSE`。
