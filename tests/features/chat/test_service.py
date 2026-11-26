from __future__ import annotations

from app.core.container import Container
from app.features.chat.prompts import SYSTEM_PROMPT, build_user_prompt
from app.features.chat.service import answer, stream_answer
from app.features.ingestion.service import ingest


def test_system_prompt_has_the_rules() -> None:
    for phrase in [
        "Answer only from the sources",
        "[title]",
        "General advice (not from Disha's knowledge base)",
        "Never promise outcomes",
        "one concrete next step",
        "₹99 Direction Call",
        "find the itch",
    ]:
        assert phrase in SYSTEM_PROMPT


def test_prompt_escapes_titles_and_marks_empty_sources() -> None:
    prompt = build_user_prompt("q?", [])
    assert "no matching sources found" in prompt
    assert "<question>\nq?\n</question>" in prompt


def test_answer_end_to_end_with_fakes(tmp_container: Container) -> None:
    ingest(tmp_container)
    result = answer(tmp_container, "How do I talk to ten real people?")
    assert result.text == "FAKE ANSWER"
    assert result.sources[0].source == "frameworks/disha-path.md"
    assert result.sources[0].title == "The Disha Path"
    assert len({s.source for s in result.sources}) == len(result.sources)

    system, prompt = tmp_container.llm.calls[-1]
    assert system == SYSTEM_PROMPT
    assert '<source title="The Disha Path" type="framework">' in prompt
    assert "How do I talk to ten real people?" in prompt


def test_stream_answer_returns_sources_then_text(tmp_container: Container) -> None:
    ingest(tmp_container)
    sources, tokens = stream_answer(tmp_container, "What is a Direction Call?")
    assert sources[0].source == "faq/direction-call.md"
    assert "".join(tokens) == "FAKE ANSWER"
