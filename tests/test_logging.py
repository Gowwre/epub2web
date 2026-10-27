import json
import zipfile
from pathlib import Path

from epub2web.cli import main

CH1 = "OEBPS/ch1.xhtml"


def _build(epub: Path, site: Path, *extra: str) -> int:
    return main([str(epub), "-o", str(site), "--force", *extra])


def test_success_writes_logs_and_artifacts(tiny_epub, tmp_path: Path):
    site = tmp_path / "site"
    assert _build(tiny_epub, site) == 0
    assert not list((tmp_path / "reports").glob("*.zip"))

    logs = list((tmp_path / "logs").glob("epub2web-*.log"))
    assert len(logs) == 1
    assert logs[0].with_suffix(".jsonl").exists()
    assert list((tmp_path / "logs").glob("*-fidelity.json"))
    assert list((tmp_path / "logs").glob("*-links.json"))
    summaries = list((tmp_path / "logs").glob("*-summary.json"))
    assert len(summaries) == 1
    summary = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert summary["status"] == "ok"
    assert summary["pages"] == 2
    text = logs[0].read_text(encoding="utf-8")
    assert "environment" in text
    assert "fidelity gate status=pass" in text
    assert "run finished status=ok" in text

    records = [
        json.loads(line)
        for line in logs[0].with_suffix(".jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(record["message"] == "run finished" for record in records)
    assert all(record["run_id"] for record in records)


def test_failure_writes_traceback_and_prints_log_path(epub_factory, tmp_path: Path, capsys):
    bad = epub_factory(
        "broken.epub",
        replacements={CH1: [(b'src="images/cover.png"', b'src="images/missing.png"')]},
    )
    assert _build(bad, tmp_path / "site") == 2
    stderr = capsys.readouterr().err
    assert "Report:" in stderr
    assert "attach this file" in stderr

    logs = list((tmp_path / "logs").glob("epub2web-*.log"))
    assert len(logs) == 1
    text = logs[0].read_text(encoding="utf-8")
    assert "Traceback" in text
    assert "missing from the EPUB" in text
    assert "run finished status=error" in text

    reports = list((tmp_path / "reports").glob("*.zip"))
    assert len(reports) == 1
    with zipfile.ZipFile(reports[0]) as archive:
        names = set(archive.namelist())
        assert {"README.txt", "run.log", "events.jsonl", "context.json"} <= names
        readme = archive.read("README.txt").decode("utf-8")
        assert "Attach this ZIP file" in readme
        assert "missing from the EPUB" in readme


def test_gate_failure_writes_artifacts(epub_factory, tmp_path: Path, capsys):
    bad_link = epub_factory(
        "bad-link.epub",
        replacements={
            CH1: [(b"</body>", b'<p><a href="missing.xhtml">broken link</a></p></body>')]
        },
    )
    site = tmp_path / "site"
    assert _build(bad_link, site) == 1
    assert not site.exists()
    assert "Report:" in capsys.readouterr().err

    reports = list((tmp_path / "reports").glob("*.zip"))
    assert len(reports) == 1
    with zipfile.ZipFile(reports[0]) as archive:
        names = set(archive.namelist())
        assert {"README.txt", "summary.json", "fidelity.json", "links.json"} <= names

    logs = list((tmp_path / "logs").glob("epub2web-*.log"))
    assert len(logs) == 1
    summaries = list((tmp_path / "logs").glob("*-summary.json"))
    assert len(summaries) == 1
    summary = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["links"]["pass"] is False
    assert list((tmp_path / "logs").glob("*-fidelity.json"))
    assert list((tmp_path / "logs").glob("*-links.json"))


def test_unwritable_log_does_not_stop_the_build(tiny_epub, tmp_path: Path, capsys):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    site = tmp_path / "site"
    code = _build(tiny_epub, site, "--log-file", str(blocker / "run.log"))
    assert code == 0
    assert (site / "index.html").exists()
    assert "file logging disabled" in capsys.readouterr().err
