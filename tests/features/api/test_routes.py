from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.adapters.llms.fake import FakeLLM
from app.core.container import Container
from app.main import create_app
from app.web import get_container


def _client(container: Container) -> TestClient:
    api = create_app()
    api.dependency_overrides[get_container] = lambda: container
    return TestClient(api)


def test_upload_ask_and_delete(kb_container: Container) -> None:
    kb_container.__dict__["llm"] = FakeLLM("Your revenue is in your P&L [S1].")
    client = _client(kb_container)

    upload = {"file": ("pnl.txt", b"Monthly revenue was 4 lakh in March.")}
    r = client.post("/businesses/biz-1/documents", files=upload,
                    data={"title": "P&L"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "indexed"

    r = client.post("/ask", json={"question": "monthly revenue March",
                                  "profile": {"business_id": "biz-1"}})
    body = r.json()
    assert body["found"] is True
    assert body["cited"] == ["S1"]

    r = client.post("/ask", json={"question": "monthly revenue March"})
    assert r.json()["found"] is False  # someone else cannot see biz-1's file

    assert client.delete("/businesses/biz-1/documents/pnl.txt").status_code == 200
    assert client.get("/health").json()["chunks"] == 0


def test_api_key_and_input_checks(kb_container: Container) -> None:
    key = {"service_api_key": SecretStr("secret")}
    locked = Container(kb_container.settings.model_copy(update=key))
    client = _client(locked)
    assert client.post("/ask", json={"question": "hello there"}).status_code == 401
    ok = client.post("/ask", json={"question": "hello there"}, headers={"X-API-Key": "secret"})
    assert ok.status_code == 200
    bad = client.post("/businesses/../documents", files={"file": ("a.txt", b"x")},
                      headers={"X-API-Key": "secret"})
    assert bad.status_code in (400, 404)
    exe = client.post("/businesses/b1/documents", files={"file": ("a.exe", b"x")},
                      headers={"X-API-Key": "secret"})
    assert exe.status_code == 400
