"""FastAPI app: serves the accessible UI and streams pipeline events via SSE."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from accesslens.config import Settings
from accesslens.pipeline import run_pipeline

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AccessLens")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/scan")
async def scan(
    url: str = Query(..., description="Page URL to scan"),
) -> StreamingResponse:
    settings = Settings.from_env()

    async def event_stream():
        async for event in run_pipeline(url, settings):
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
