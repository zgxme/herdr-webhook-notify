import base64
import hashlib
import hmac
import json
import urllib.parse

from herdr_webhook_notify import providers
from herdr_webhook_notify.providers import base


def message(kind="done"):
    return base.Message(
        kind=kind,
        status="done",
        title="Herdr Task finished: do the thing",
        body="**Status**: Task finished",
        fields={"workspace": "w1"},
        timestamp=1700000000,
    )


def payload(delivery):
    return json.loads(delivery.body.decode("utf-8"))


def test_registry_covers_expected_providers():
    assert providers.names() == [
        "dingtalk",
        "discord",
        "feishu",
        "generic",
        "google_chat",
        "lark",
        "ntfy",
        "slack",
        "teams",
        "telegram",
        "wecom",
    ]


def test_feishu_card_payload():
    module = providers.get("feishu")
    delivery = module.build({"webhook_url": "https://example.com/hook"}, message())
    body = payload(delivery)
    assert body["msg_type"] == "interactive"
    assert body["card"]["header"]["template"] == "green"
    assert body["card"]["elements"][0]["content"] == "**Status**: Task finished"


def test_feishu_signature_matches_documented_algorithm():
    module = providers.get("feishu")
    signature = module.sign("s3cret", 1700000000)
    expected = base64.b64encode(
        hmac.new(b"1700000000\ns3cret", b"", hashlib.sha256).digest()
    ).decode()
    assert signature == expected

    delivery = module.build(
        {"webhook_url": "https://example.com/hook", "secret": "s3cret"}, message()
    )
    body = payload(delivery)
    assert body["timestamp"] == "1700000000"
    assert body["sign"] == expected


def test_lark_reuses_the_feishu_protocol_under_its_own_name():
    lark = providers.get("lark")
    feishu = providers.get("feishu")
    options = {"webhook_url": "https://open.larksuite.com/open-apis/bot/v2/hook/abc", "secret": "s3cret"}
    lark_delivery = lark.build(options, message())
    feishu_delivery = feishu.build(options, message())
    assert lark_delivery.provider == "lark"
    assert lark_delivery.body == feishu_delivery.body
    assert lark_delivery.url == feishu_delivery.url
    assert payload(lark_delivery)["card"]["header"]["title"]["content"].startswith("Herdr Task finished")


def test_dingtalk_signature_is_appended_to_the_url():
    module = providers.get("dingtalk")
    timestamp_ms = 1700000000000
    expected = urllib.parse.quote_plus(
        base64.b64encode(
            hmac.new(b"s3cret", f"{timestamp_ms}\ns3cret".encode(), hashlib.sha256).digest()
        ).decode()
    )
    url = module.signed_url("https://example.com/hook?a=1", "s3cret", timestamp_ms)
    assert url == f"https://example.com/hook?a=1&timestamp={timestamp_ms}&sign={expected}"


def test_slack_uses_mrkdwn_single_asterisks():
    module = providers.get("slack")
    # The CLI converts Markdown to the provider flavor before calling build().
    m = message()
    m.body = "*Status*: Task finished"
    delivery = module.build({"webhook_url": "https://example.com/hook"}, m)
    body = payload(delivery)
    assert body["blocks"][0]["text"]["text"].startswith("*Herdr Task finished: do the thing*")
    assert "**" not in body["blocks"][0]["text"]["text"]


def test_discord_embed_color_and_timestamp():
    module = providers.get("discord")
    delivery = module.build({"webhook_url": "https://example.com/hook"}, message("blocked"))
    body = payload(delivery)
    assert body["embeds"][0]["color"] == 0xECB22E
    assert body["embeds"][0]["timestamp"] == "2023-11-14T22:13:20Z"


def test_teams_message_card():
    module = providers.get("teams")
    delivery = module.build({"webhook_url": "https://example.com/hook"}, message())
    body = payload(delivery)
    assert body["@type"] == "MessageCard"
    assert body["themeColor"] == "2EB67D"


def test_google_chat_uses_slack_style_bold():
    module = providers.get("google_chat")
    delivery = module.build({"webhook_url": "https://example.com/hook"}, message())
    assert payload(delivery)["text"].startswith("*Herdr Task finished")


def test_wecom_builds_url_from_key():
    module = providers.get("wecom")
    delivery = module.build({"key": "abc"}, message())
    assert delivery.url.endswith("?key=abc")
    assert payload(delivery)["markdown"]["content"].startswith("### Herdr Task finished")


def test_telegram_plain_and_html_modes():
    module = providers.get("telegram")
    delivery = module.build({"bot_token": "t", "chat_id": "1"}, message())
    body = payload(delivery)
    assert delivery.url.endswith("/bott/sendMessage")
    assert body["text"].startswith("Herdr Task finished")
    assert "parse_mode" not in body

    delivery = module.build({"bot_token": "t", "chat_id": "1", "parse_mode": "HTML"}, message())
    assert payload(delivery)["parse_mode"] == "HTML"


def test_telegram_markdown_v2_escapes_reserved_characters():
    module = providers.get("telegram")
    m = message()
    m.body = "**Status**: Task finished (2.0)"
    delivery = module.build({"bot_token": "t", "chat_id": "1", "parse_mode": "MarkdownV2"}, m)
    text = payload(delivery)["text"]
    assert "*Status*" in text
    assert "\\." in text
    assert "\\(" in text


def test_ntfy_headers_and_body():
    module = providers.get("ntfy")
    delivery = module.build({"topic": "alerts"}, message("blocked"))
    assert delivery.url == "https://ntfy.sh/alerts"
    assert delivery.headers["Priority"] == "high"
    assert delivery.body.decode().startswith("Herdr Task finished")


def test_generic_default_payload():
    module = providers.get("generic")
    delivery = module.build({"url": "https://example.com/hook"}, message())
    body = payload(delivery)
    assert body["kind"] == "done"
    assert body["fields"] == {"workspace": "w1"}


def test_generic_custom_body_template():
    module = providers.get("generic")
    delivery = module.build(
        {"url": "https://example.com/hook", "body": "task={task}\nkeep={unknown}"}, message()
    )
    assert delivery.body.decode() == "task={task}\nkeep={unknown}"
