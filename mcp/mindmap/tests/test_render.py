"""M-2: pure-logic tests for the mind-map renderer."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from mcp_mindmap.render import to_mermaid, to_svg

SAMPLE = {
    "text": "Cloud Concepts",
    "children": [
        {"text": "Benefits", "children": [{"text": "Elasticity"}, {"text": "Pay-as-you-go"}]},
        {"text": "Economics", "children": [{"text": "CapEx vs OpEx"}]},
    ],
}


def test_to_mermaid_starts_with_mindmap_directive() -> None:
    out = to_mermaid(SAMPLE)
    lines = out.splitlines()
    assert lines[0] == "mindmap"
    # root form: ``root((Text))``
    assert "root((Cloud Concepts))" in out
    # Children appear indented.
    assert "Benefits" in out
    assert "Elasticity" in out


def test_to_svg_is_valid_xml() -> None:
    out = to_svg(SAMPLE)
    root = ET.fromstring(out)
    # The default namespace makes the tag `{http://www.w3.org/2000/svg}svg`.
    assert root.tag.endswith("}svg") or root.tag == "svg"
    # SVG should contain at least one circle and one text element.
    ns = "{http://www.w3.org/2000/svg}"
    assert root.findall(f"{ns}circle"), "no circles rendered"
    assert root.findall(f"{ns}text"), "no text rendered"


def test_to_svg_includes_root_text() -> None:
    out = to_svg(SAMPLE)
    assert "Cloud Concepts" in out
    assert "Benefits" in out
    assert "Pay-as-you-go" in out


def test_to_svg_handles_empty_children() -> None:
    out = to_svg({"text": "Solo"})
    root = ET.fromstring(out)
    assert root.tag.endswith("}svg")
    # Just the root circle + label.
    assert "Solo" in out
