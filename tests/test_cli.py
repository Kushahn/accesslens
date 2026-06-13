import json

from accesslens.cli import main

DEMO_URL = "https://demo.accesslens.example/broken-page"


def test_scan_mock_writes_json_and_logs(tmp_path, capsys):
    out = tmp_path / "plan.json"
    code = main(["scan", DEMO_URL, "--mock", "--json", str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["steps"], "exported plan should contain steps"
    captured = capsys.readouterr()
    assert "scanner" in captured.out  # streaming reasoning log was printed


def test_scan_mock_writes_html_quietly(tmp_path, capsys):
    out = tmp_path / "report.html"
    code = main(["scan", DEMO_URL, "--mock", "--html", str(out), "--quiet"])
    assert code == 0
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")
    captured = capsys.readouterr()
    assert "[scanner]" not in captured.out  # --quiet suppresses the log


def test_scan_blocked_url_returns_nonzero(tmp_path):
    code = main(["scan", "file:///etc/passwd", "--mock"])
    assert code != 0


def test_no_command_returns_usage_code(capsys):
    code = main([])
    assert code == 2
