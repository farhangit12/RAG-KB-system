from __future__ import annotations

import pytest
from typer.testing import CliRunner

from app import cli
from app.core.config import Settings


def test_info_never_prints_the_key(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    secret = settings.model_copy(update={"anthropic_api_key": "sk-should-not-show"})
    monkeypatch.setattr(cli, "get_settings", lambda: secret)
    result = CliRunner().invoke(cli.app, ["info"])
    assert result.exit_code == 0, result.output
    assert "api key set:    yes" in result.output
    assert "sk-should-not-show" not in result.output
    assert "4 markdown files" in result.output
