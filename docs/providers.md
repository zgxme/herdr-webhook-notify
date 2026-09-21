# Providers

Every provider is configured in the `[providers.<name>]` table. Only tables with
`enabled = true` are used. Values can reference environment variables with
`${NAME}`, which makes it easy to keep secrets in a `.env` file next to
`config.toml`.

Common options for every provider:

| option | meaning |
| --- | --- |
| `enabled` | `true` to use this provider |
| `events` | optional subset of `done`, `blocked`, `unknown`, `exited` |
| `language` | optional language override (`en`, `zh-CN`) |

## feishu

Feishu (Lark) custom bot webhook.

1. Group settings, then `Bots`, `Add bot`, `Custom bot`.
2. Copy the webhook URL, and the signing secret if you enabled signature
   verification.

```toml
[providers.feishu]
enabled = true
webhook_url = "${FEISHU_WEBHOOK}"
secret = "${FEISHU_SECRET}"   # optional
format = "card"               # card | text
card_title_prefix = ""        # optional prefix for the card header
```

Signature mode adds `timestamp` and `sign` to the payload using
`base64(hmac_sha256(key="<timestamp>\n<secret>", msg=""))`, which is what Feishu
documents for custom bots.

## lark

Lark is the international edition of Feishu. Bots use the same protocol, only
the host differs (`open.larksuite.com` instead of `open.feishu.cn`), so this
provider accepts the same options and produces the same card:

```toml
[providers.lark]
enabled = true
webhook_url = "${LARK_WEBHOOK}"
secret = "${LARK_SECRET}"     # optional
format = "card"               # card | text
```

Pick `feishu` or `lark` based on the tenant you created the bot in; both can be
enabled at once if your team spans both.

## dingtalk

DingTalk custom robot. Enable `加签` in the robot security settings if you want
signature verification.

```toml
[providers.dingtalk]
enabled = true
webhook_url = "${DINGTALK_WEBHOOK}"
secret = "${DINGTALK_SECRET}"   # optional
```

With a secret, `timestamp` and `sign` are appended to the URL as query
parameters.

## wecom

WeCom (WeChat Work) group robot. Paste the robot key or the whole webhook URL.

```toml
[providers.wecom]
enabled = true
key = "${WECOM_KEY}"
# webhook_url = "${WECOM_WEBHOOK}"
# base_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"
```

## slack

Slack incoming webhook. Create an app, enable `Incoming Webhooks`, then add a
webhook to the channel you want.

```toml
[providers.slack]
enabled = true
webhook_url = "${SLACK_WEBHOOK}"
```

Messages use Block Kit with a `mrkdwn` section; Markdown from your template is
converted to Slack's single-asterisk bold.

## discord

Channel settings, `Integrations`, `Webhooks`, `New Webhook`, then copy the URL.

```toml
[providers.discord]
enabled = true
webhook_url = "${DISCORD_WEBHOOK}"
username = "Herdr"            # optional
avatar_url = ""               # optional
content = "<@&1234567890>"    # optional mention outside the embed
```

The card is sent as an embed whose color follows the event kind.

## teams

Microsoft Teams incoming webhook (MessageCard).

```toml
[providers.teams]
enabled = true
webhook_url = "${TEAMS_WEBHOOK}"
```

Newer Teams tenants may require a Workflows connector instead; if so, use the
`generic` provider and point it at the Workflow trigger URL.

## google_chat

Google Chat space webhook (`Space settings`, `Apps & integrations`,
`Webhooks`).

```toml
[providers.google_chat]
enabled = true
webhook_url = "${GOOGLE_CHAT_WEBHOOK}"
thread_key = ""               # optional, keeps messages in one thread
```

## telegram

Telegram uses the Bot API instead of a webhook URL.

1. Talk to `@BotFather`, create a bot, copy the token.
2. Send the bot a message, then read `chat_id` from
   `https://api.telegram.org/bot<token>/getUpdates`.

```toml
[providers.telegram]
enabled = true
bot_token = "${TELEGRAM_BOT_TOKEN}"
chat_id = "${TELEGRAM_CHAT_ID}"
parse_mode = ""               # "", HTML or MarkdownV2
message_thread_id = ""        # optional forum topic
disable_notification = false
```

Without `parse_mode` the message is plain text, which is the safest default.

## ntfy

Push notifications through ntfy.sh or your own server.

```toml
[providers.ntfy]
enabled = true
url = "https://ntfy.sh"       # optional
topic = "${NTFY_TOPIC}"
token = "${NTFY_TOKEN}"       # optional
priority = ""                 # default: high for blocked/unknown/exited
tags = "robot"                # optional
click = ""                    # optional URL opened when tapping
```

## generic

Anything else: an internal alerting gateway, a Zapier/Make hook, a custom
script. You control the method, the headers, and the body.

```toml
[providers.generic]
enabled = true
url = "${GENERIC_WEBHOOK_URL}"
method = "POST"                       # POST | PUT | PATCH
content_type = "application/json"
headers = { Authorization = "Bearer ${GENERIC_TOKEN}" }

# Default payload when no body is given:
# {"title": ..., "body": ..., "kind": ..., "status": ..., "fields": {...}}
body = '{"text": "{title}\n{body}", "workspace": "{workspace}"}'
flavor = "markdown"                   # markdown | slack | plain
```

Body templates support the same placeholders as `[message]` in `config.toml`.
Only `{name}` placeholders are substituted, so JSON braces survive untouched
and the example above works as written. Format specs such as `{duration_seconds:.0f}`
are a `[message]`-only convenience and are left alone here.
