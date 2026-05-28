import pytest

from marktplaats_monitor.cli import main


def test_stats_empty_db(tmp_path, capsys):
    rc = main(["stats", "--db", str(tmp_path / "s.sqlite3")])
    assert rc == 0
    assert "No data yet" in capsys.readouterr().out


def test_config_error_returns_2(tmp_path, caplog):
    bad = tmp_path / "config.yaml"
    bad.write_text("searches: []\n", encoding="utf-8")
    rc = main(["once", "--config", str(bad), "--db", str(tmp_path / "s.sqlite3")])
    assert rc == 2


def test_missing_config_returns_2(tmp_path):
    rc = main(["run", "--config", str(tmp_path / "nope.yaml"), "--db", str(tmp_path / "s.sqlite3")])
    assert rc == 2


def test_unknown_command_exits():
    with pytest.raises(SystemExit):
        main(["frobnicate"])


def test_once_runs_with_valid_config(tmp_path, monkeypatch):
    monkeypatch.setenv("APPRISE_URLS", "ntfy://ntfy.sh/whatever")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "searches:\n"
        "  - id: a\n"
        "    url: https://www.marktplaats.nl/q/a/\n"
        "    notify: {apprise_urls: ['env:APPRISE_URLS']}\n",
        encoding="utf-8",
    )
    # Avoid real network: stub the client search on every runtime.
    import marktplaats_monitor.monitor as mon

    monkeypatch.setattr(mon.MarktplaatsClient, "search", lambda self, *a, **k: [])
    rc = main(["once", "--config", str(cfg), "--db", str(tmp_path / "s.sqlite3")])
    assert rc == 0
