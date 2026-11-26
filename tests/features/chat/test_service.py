from __future__ import annotations

from app.adapters.llms.fake import FakeLLM
from app.adapters.tokenizers.estimate import EstimateTokenCounter
from app.core.container import Container
from app.core.ports import Chunk
from app.features.chat.models import Source
from app.features.chat.packing import citation, pack
from app.features.chat.prompts import NOT_FOUND
from app.features.chat.service import answer, check_citations


def _add(container: Container, cid: str, text: str, **meta) -> None:
    meta.setdefault("visibility", "public")
    meta.setdefault("title", cid)
    chunk = Chunk(id=cid, source=cid.split("#")[0], text=text, metadata=meta)
    container.vector_store.upsert([chunk], container.embedder.embed([text]))


def test_not_found_skips_the_llm(container: Container) -> None:
    llm = FakeLLM()
    container.__dict__["llm"] = llm
    result = answer(container, "quantum chromodynamics lattice")
    assert result.answer == NOT_FOUND
    assert result.found is False
    assert llm.calls == []


def test_answer_with_valid_and_invalid_citations(container: Container) -> None:
    _add(container, "faq/seed.md#0", "Seed funding is the first outside money a startup raises.",
         title="Seed funding basics", page_start=2, publisher="Disha", publication_year=2026)
    container.__dict__["llm"] = FakeLLM("It is early money [S1]. Also [S9].")
    result = answer(container, "What is seed funding money?")
    assert result.found
    assert result.cited == ["S1"]
    assert result.invalid_citations == ["S9"]
    assert "[S9]" not in result.answer
    assert result.sources[0].citation == "Seed funding basics, p. 2, Disha 2026"
    system, prompt = container.llm.calls[0]
    assert "[S1] Seed funding basics" in prompt
    assert result.prompt_tokens <= container.settings.max_input_tokens


def test_uncited_answer_is_low_confidence(container: Container) -> None:
    _add(container, "a.md#0", "pricing strategy for founders")
    container.__dict__["llm"] = FakeLLM("Charge more.")
    assert answer(container, "pricing strategy founders").low_confidence


def test_pack_respects_budget_and_prefers_newer_on_ties() -> None:
    old = Chunk("old#0", "old", "word " * 300, {"title": "Old", "publication_year": 2019})
    new = Chunk("new#0", "new", "word " * 300, {"title": "New", "publication_year": 2025})
    sources = pack([(old, 0.80), (new, 0.79)], EstimateTokenCounter(), budget=450)
    assert [s.source for s in sources] == ["new"]


def test_check_citations_and_citation_format() -> None:
    src = [Source("S1", "a#0", "a", "A", "t", 0.9)]
    text, cited, invalid = check_citations("x [S1] y [S2] [S1]", src)
    assert (cited, invalid) == (["S1"], ["S2"])
    assert "[S2]" not in text
    chunk = Chunk("r#0", "r.pdf", "t", {"title": "Report", "page_start": 3, "page_end": 5})
    assert citation(chunk) == "Report, pp. 3-5"
