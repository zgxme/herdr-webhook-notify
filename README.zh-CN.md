<div align="center">

# herdr-webhook-notify

[![CI](https://github.com/zgxme/herdr-webhook-notify/actions/workflows/ci.yml/badge.svg)](https://github.com/zgxme/herdr-webhook-notify/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml) [![Herdr plugin](https://img.shields.io/badge/Herdr-plugin-6E56CF.svg)](https://herdr.dev/plugins/) [![Providers](https://img.shields.io/badge/providers-11-2EB67D.svg)](#支持的服务商)

把 [Herdr](https://herdr.dev) 的 agent 通知转发到你已经在用的渠道：飞书、钉钉、
Lark、企业微信、Slack、Discord、Microsoft Teams、Google Chat、Telegram、ntfy，
或者任意自定义 HTTP 接口。

[English](README.md) | [服务商配置指南](docs/providers.md) | [参与贡献](CONTRIBUTING.md)

</div>

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

## 配置

配置文件位于 `herdr plugin config-dir herdr-webhook-notify` 打印的目录中。密钥可以放在
同目录的 `.env` 里，用 `${NAME}` 引用；已经存在于进程环境中的变量优先，方便配合 CI 和
密钥管理。

```toml
language = "zh-CN"                   # en | zh-CN

[notify]
events = ["done", "blocked", "unknown", "exited"]
notify_when_focused = true           # false = 只看后台 pane，盯着看时不打扰
min_turn_seconds = 0                 # 太短的 turn 不通知
cooldown_seconds = 5                 # 同一 pane 同类型去重
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

可用占位符：`{status}`、`{status_label}`、`{kind}`、`{session}`、`{workspace}`、
`{workspace_id}`、`{tab}`、`{tab_id}`、`{task}`、`{agent}`、`{pane_id}`、`{cwd}`、
`{branch}`、`{duration}`、`{duration_seconds}`、`{host}`、`{time}`。未知占位符会原样
保留；值为空的行会自动删除，所以像 `{branch}` 这种可选字段不会留下空标签。

## 支持的服务商

`feishu`、`lark`、`dingtalk`、`wecom`、`slack`、`discord`、`teams`、`google_chat`、
`telegram`、`ntfy`、`generic`。每个服务商的申请步骤和专属参数见
[docs/providers.md](docs/providers.md)。

## 命令（Actions）

| action | 作用 |
| --- | --- |
| `herdr-webhook-notify.init` | 写出带注释的 `config.toml` |
| `herdr-webhook-notify.test` | 给所有启用的 provider 发一条测试消息 |
| `herdr-webhook-notify.status` | 显示配置路径、provider、过滤规则和待重投队列 |
| `herdr-webhook-notify.mute` / `.resume` | 不改配置临时静音 / 恢复 |

## 可靠性

- hook 不会阻塞 Herdr：短超时、退出码 0、错误只写 stderr。
- 408/425/429/5xx 会做有限重试。
- 仍失败的通知会落到插件状态目录，下一次事件时重投，最多三次。
- 日志和 `status` 输出会隐藏 webhook URL 中的密钥片段。

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
