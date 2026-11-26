from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.container import Container
from app.core.ports import LLMError
from app.features.ingestion.service import ingest
from app.main import create_app

ORIGIN = "https://disha-advisory-vert.vercel.app"


def _client(container: Container) -> TestClient:
    return TestClient(create_app(container.settings, container))


@pytest.fixture
def client(tmp_container: Container) -> TestClient:
    ingest(tmp_container)
    return _client(tmp_container)


def _events(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_returns_answer_and_sources(client: TestClient, tmp_container: Container) -> None:
    res = client.post(
        "/chat",
        json={"question": "How do I talk to ten real people?", "user_context": {"stage": "idea"}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == "FAKE ANSWER"
    assert body["sources"][0] == {
        "title": "The Disha Path",
        "source": "frameworks/disha-path.md",
        "type": "framework",
        "score": body["sources"][0]["score"],
    }
    _, prompt = tmp_container.llm.calls[-1]
    assert "<asker>\nstage: idea\n</asker>" in prompt


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 1001},
        {"question": "hi", "user_context": {"stage": "unicorn"}},
        {"question": "hi", "user_context": {"sector": "s" * 61}},
        {"question": "hi", "extra": 1},
    ],
)
def test_input_validation(client: TestClient, payload: dict) -> None:
    assert client.post("/chat", json=payload).status_code == 422


def test_stream_sends_sources_tokens_done(client: TestClient) -> None:
    res = client.post("/chat/stream", json={"question": "What is a Direction Call?"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    events = _events(res.text)
    assert events[0][0] == "sources"
    assert events[0][1]["sources"][0]["source"] == "faq/direction-call.md"
    assert "".join(d["text"] for e, d in events if e == "token") == "FAKE ANSWER"
    assert events[-1] == ("done", {})


class _BrokenLLM:
    def generate(self, system: str, prompt: str) -> str:
        raise LLMError("down")

    def stream(self, system: str, prompt: str) -> Iterator[str]:
        yield "partial "
        raise LLMError("down")


def test_llm_failure_is_502_and_stream_error_event(tmp_container: Container) -> None:
    tmp_container.__dict__["llm"] = _BrokenLLM()
    client = _client(tmp_container)
    res = client.post("/chat", json={"question": "hi"})
    assert res.status_code == 502
    assert "unavailable" in res.json()["detail"]
    events = _events(client.post("/chat/stream", json={"question": "hi"}).text)
    assert events[-1][0] == "error"


def test_cors_only_allows_disha_origin(client: TestClient) -> None:
    preflight = {"Access-Control-Request-Method": "POST"}
    ok = client.options("/chat", headers={"Origin": ORIGIN, **preflight})
    assert ok.headers.get("access-control-allow-origin") == ORIGIN
    bad = client.options("/chat", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in bad.headers


def test_rate_limit_returns_429(tmp_container: Container) -> None:
    limited = Container(tmp_container.settings.model_copy(update={"rate_limit_requests": 2}))
    client = _client(limited)
    codes = [client.post("/chat", json={"question": "hi"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    res = client.post("/chat", json={"question": "hi"})
    assert res.headers["retry-after"] == "60"
