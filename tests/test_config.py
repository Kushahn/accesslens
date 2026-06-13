from accesslens.config import Settings


def test_defaults_to_live_scanning(monkeypatch):
    monkeypatch.delenv("ACCESSLENS_MOCK", raising=False)
    monkeypatch.delenv("ACCESSLENS_ALLOW_LOCAL", raising=False)
    settings = Settings.from_env()
    # The product scans real URLs by default; mock is opt-in.
    assert settings.mock is False
    # Private/local hosts stay blocked unless explicitly allowed (SSRF guard).
    assert settings.allow_local is False


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("ACCESSLENS_MOCK", "0")
    monkeypatch.setenv("ACCESSLENS_ALLOW_LOCAL", "1")
    settings = Settings.from_env()
    assert settings.mock is False
    assert settings.allow_local is True
