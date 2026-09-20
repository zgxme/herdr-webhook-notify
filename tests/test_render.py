from herdr_webhook_notify import markup, render


def test_unknown_placeholder_is_kept():
    assert render.render("Herdr {status_label}", {}) == "Herdr {status_label}"


def test_known_placeholders_are_replaced():
    assert render.render("{a}-{b}", {"a": "1", "b": "2"}) == "1-2"


def test_empty_label_lines_are_dropped():
    text = "\n".join(
        [
            "**Status**: done",
            "**Branch**: ",
            "**Cwd**: /tmp/x",
            "",
            "**Directory**：",
        ]
    )
    assert render.drop_empty_lines(text) == "**Status**: done\n**Cwd**: /tmp/x"


def test_slack_flavor_converts_bold():
    assert markup.convert("**Status**: done", "slack") == "*Status*: done"


def test_plain_flavor_strips_markers():
    assert markup.convert("**Status**: done", "plain") == "Status: done"


def test_duration_formatting():
    assert render.format_duration(12) == "12s"
    assert render.format_duration(125) == "2m05s"
    assert render.format_duration(3725) == "1h02m"
    assert render.format_duration(None) == ""
