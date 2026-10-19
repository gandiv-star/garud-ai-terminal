"""Repository rules: pinned dependencies, no secrets committed, workflows keep live OFF elsewhere."""
import os
import re

from helpers import ROOT, ROOT_FILE


def test_every_dependency_has_an_upper_bound():
    lines = [l.strip() for l in open(ROOT_FILE("requirements.txt"), encoding="utf-8")
             if l.strip() and not l.strip().startswith("#")]
    assert len(lines) >= 12
    for l in lines:
        assert ">=" in l and "<" in l, f"not pinned: {l}"


def test_only_rule_workflow_can_see_live_settings():
    wf_dir = ROOT_FILE(".github/workflows")
    for name in os.listdir(wf_dir):
        if not name.endswith(".yml") or name == "rule_paper_trading.yml":
            continue
        text = open(os.path.join(wf_dir, name), encoding="utf-8").read()
        assert "LIVE_ORDERS_ENABLED" not in text and "BROKER_ACCESS_TOKEN" not in text, name


def test_no_secret_looking_values_in_python_files():
    pattern = re.compile(r"(eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})|(AIza[0-9A-Za-z_-]{30,})|(\d{9,10}:AA[0-9A-Za-z_-]{30,})")
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".venv", "venv")]
        for f in files:
            if f.endswith((".py", ".yml", ".toml", ".txt", ".md")):
                text = open(os.path.join(base, f), encoding="utf-8", errors="ignore").read()
                assert not pattern.search(text), os.path.join(base, f)
