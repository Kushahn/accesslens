from accesslens.config import Settings
from accesslens.models import EventType
from accesslens.pipeline import run_pipeline


def mock_settings(**overrides) -> Settings:
    defaults = dict(mock=True, allow_local=False, foundry_endpoint="", foundry_model="")
    defaults.update(overrides)
    return Settings(**defaults)


async def collect(url: str, settings: Settings):
    return [event async for event in run_pipeline(url, settings)]


async def test_mock_pipeline_completes_with_plan():
    events = await collect(
        "https://demo.accesslens.example/broken-page", mock_settings()
    )
    types = [e.type for e in events]
    assert types[-1] == EventType.DONE
    done = events[-1]
    assert done.payload["plan"]["steps"], "DONE event must carry the plan"
    stages = {e.stage for e in events}
    assert {
        "scanner",
        "standards_mapper",
        "impact_assessor",
        "remediation_planner",
    } <= stages


async def test_guardrail_block_emits_error_event():
    events = await collect("file:///etc/passwd", mock_settings())
    assert events[-1].type == EventType.ERROR
    assert "http" in events[-1].message.lower()


async def test_guardrail_results_are_streamed():
    events = await collect(
        "https://demo.accesslens.example/broken-page", mock_settings()
    )
    guardrail_events = [e for e in events if e.type == EventType.GUARDRAIL]
    assert guardrail_events, "guardrail outcomes must be visible in the event log"
