import httpx
import pytest

from accesslens.web.app import app


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("ACCESSLENS_MOCK", "1")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_index_serves_html(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


async def test_scan_streams_events_ending_in_done(client):
    async with client.stream(
        "GET",
        "/api/scan",
        params={"url": "https://demo.accesslens.example/broken-page"},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = ""
        async for chunk in response.aiter_text():
            body += chunk
    assert '"done"' in body
    assert '"guardrail"' in body
