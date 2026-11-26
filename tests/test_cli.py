from __future__ import annotations

import pytest
from typer.testing import CliRunner

from app import cli
from app.core.config import Settings
from app.core.container import Container


def test_info_never_prints_the_key(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    secret = settings.model_copy(update={"anthropic_api_key": "sk-should-not-show"})
    monkeypatch.setattr(cli, "get_settings", lambda: secret)
    result = CliRunner().invoke(cli.app, ["info"])
    assert result.exit_code == 0, result.output
    assert "api key set:    yes" in result.output
    assert "sk-should-not-show" not in result.output
    assert "4 markdown files" in result.output


def test_ingest_then_ask(monkeypatch: pytest.MonkeyPatch, tmp_container: Container) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: tmp_container.settings)
    monkeypatch.setattr(cli, "_container", lambda: tmp_container)
    runner = CliRunner()

    ingested = runner.invoke(cli.app, ["ingest"])
    assert ingested.exit_code == 0, ingested.output
    assert "added 4, updated 0, unchanged 0, removed 0" in ingested.output

    again = runner.invoke(cli.app, ["ingest"])
    assert "added 0, updated 0, unchanged 4, removed 0; 0 chunks written" in again.output

    asked = runner.invoke(cli.app, ["ask", "What is the Disha Path?"])
    assert asked.exit_code == 0, asked.output
    assert "FAKE ANSWER" in asked.output
    assert "[The Disha Path] (frameworks/disha-path.md" in asked.output

    filtered = runner.invoke(cli.app, ["ask", "What is the Disha Path?", "--type", "faq"])
    assert "(faq/direction-call.md" in filtered.output
    assert "frameworks/disha-path.md" not in filtered.output
