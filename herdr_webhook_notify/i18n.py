"""Built-in message catalog.

English is the default. Users can pick another language in config.toml or
override single strings with the [messages] table.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "en"

LOCALES = {
    "en": {
        "status.done": "Task finished",
        "status.blocked": "Needs attention",
        "status.unknown": "State unknown",
        "status.exited": "Session process exited",
        "status.test": "Test notification",
        "title": "Herdr {status_label}: {task}",
        "body": "\n".join(
            [
                "**Status**: {status_label}",
                "**Session**: {session}",
                "**Workspace**: {workspace}",
                "**Tab**: {tab}",
                "**Task**: {task}",
                "**Agent**: {agent}",
                "**Pane**: {pane_id}",
                "**Directory**: {cwd}",
                "**Branch**: {branch}",
                "**Duration**: {duration}",
                "**Host**: {host}",
                "**Time**: {time}",
            ]
        ),
    },
    "zh-CN": {
        "status.done": "任务完成",
        "status.blocked": "需要人工介入",
        "status.unknown": "状态未知，可能异常",
        "status.exited": "会话进程退出",
        "status.test": "测试通知",
        "title": "Herdr {status_label}：{task}",
        "body": "\n".join(
            [
                "**状态**：{status_label}",
                "**会话**：{session}",
                "**工作区**：{workspace}",
                "**Tab**：{tab}",
                "**任务**：{task}",
                "**Agent**：{agent}",
                "**Pane**：{pane_id}",
                "**目录**：{cwd}",
                "**分支**：{branch}",
                "**耗时**：{duration}",
                "**主机**：{host}",
                "**时间**：{time}",
            ]
        ),
    },
}


def available() -> list:
    return sorted(LOCALES)


def normalize(language: str) -> str:
    """Accept en, EN, zh, zh-cn, zh_CN and map them onto a known locale."""
    if not language:
        return DEFAULT_LANGUAGE
    candidate = language.strip().replace("_", "-")
    lowered = {name.lower(): name for name in LOCALES}
    if candidate.lower() in lowered:
        return lowered[candidate.lower()]
    base = candidate.split("-", 1)[0].lower()
    if base in lowered:
        return lowered[base]
    return DEFAULT_LANGUAGE


def translate(language: str, key: str, overrides: dict = None) -> str:
    overrides = overrides or {}
    if key in overrides:
        value = overrides[key]
        if isinstance(value, str):
            return value

    locale = normalize(language)
    catalog = LOCALES.get(locale, LOCALES[DEFAULT_LANGUAGE])
    if key in catalog:
        return catalog[key]
    fallback = LOCALES[DEFAULT_LANGUAGE]
    return fallback.get(key, key)


def status_label(language: str, kind: str, overrides: dict = None) -> str:
    return translate(language, f"status.{kind}", overrides)
