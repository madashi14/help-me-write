import json

from conftest import ROOT


def test_claude_manifest():
    m = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert m["name"] == "help-me-write" and m["version"] == "0.1.0"


def test_claude_marketplace_points_to_repo_root():
    m = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert m["plugins"][0]["name"] == "help-me-write" and m["plugins"][0]["source"] == "./"


def test_codex_manifest():
    m = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    assert m["name"] == "help-me-write" and m["skills"] == "./skills/"
    assert m["interface"]["displayName"] == "Help Me Write"


def test_codex_marketplace():
    m = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    assert m["plugins"][0]["source"] == {"source": "url", "url": "./"}
