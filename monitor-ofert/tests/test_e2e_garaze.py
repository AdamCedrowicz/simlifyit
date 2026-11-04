"""Pełny przebieg modułu garaży na lokalnym serwerze: punkt wyjścia, nowości, ponowienie po błędzie maila."""
import http.server
import threading
from pathlib import Path

import pytest

import monitor.core.run as run_mod
import monitor.garaze.module as gm
from monitor.core.run import RunOptions

BASE = {
    "/lista": "<html><body><ul><li><a href='/ogl/1'>Przetarg na sprzedaż garażu przy ul. Polnej</a></li>"
              "<li><a href='/ogl/2'>Ogłoszenie o przetargu nr 2/2026</a></li></ul></body></html>",
    "/ogl/1": "<p>Sprzedaż garażu</p>",
    "/ogl/2": "<p>Prezydent ogłasza przetarg na sprzedaż garażu nr 9, cena wywoławcza 30 000 zł.</p>",
}


PAGES: dict = {}


@pytest.fixture
def server():
    PAGES.clear()
    PAGES.update(BASE)
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = PAGES.get(self.path)
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write((body or "").encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture
def env(tmp_path, monkeypatch, server):
    sent = []
    sites = [{"name": "Test BIP", "city": "Katowice", "type": "urzad", "url": server + "/lista", "enabled": True},
             {"name": "Martwa", "city": "X", "type": "urzad", "url": server + "/brak", "enabled": True}]
    monkeypatch.setattr(gm, "load_json", lambda name: sites)
    monkeypatch.setattr(gm, "DATA_DIR", tmp_path)
    monkeypatch.setattr(gm, "load_config", lambda: {"garaze": {"delayBetweenRequestsMs": 0, "failureAlertAfter": 2}})
    monkeypatch.setattr(run_mod, "send_mail", lambda subj, body, text=None: sent.append((subj, body)))
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    return sent, tmp_path


def test_przebiegi(env):
    sent, tmp = env
    r = gm.run(RunOptions())  # pierwszy przebieg: punkt wyjścia, bez maila
    assert [s.ok for s in r.statuses] == [True, False]
    assert sent == []
    PAGES["/lista"] = PAGES["/lista"].replace("</ul>", "<li><a href='/ogl/3'>Sprzedaż garażu nr 4</a></li></ul>")
    gm.run(RunOptions())  # drugi: jedna nowość + alert o martwej stronie (2 błędy z rzędu)
    subjects = [s for s, _ in sent]
    assert subjects[0] == "NOWE garaże na sprzedaż: 1"
    assert "ogl/3" in sent[0][1]
    assert any("nie działa" in s for s in subjects)
    n = len(sent)
    gm.run(RunOptions())  # trzeci: nic nowego, alert już był
    assert len(sent) == n


def test_blad_maila_ponowienie(env, monkeypatch):
    sent, tmp = env
    gm.run(RunOptions())
    PAGES["/lista"] = PAGES["/lista"].replace("</ul>", "<li><a href='/ogl/5'>Sprzedaż garażu nr 5</a></li></ul>")

    def boom(*a, **k):
        raise OSError("SMTP niedostępny")
    monkeypatch.setattr(run_mod, "send_mail", boom)
    with pytest.raises(OSError):
        gm.run(RunOptions())
    monkeypatch.setattr(run_mod, "send_mail", lambda s, b, t=None: sent.append((s, b)))
    gm.run(RunOptions())
    assert any("ogl/5" in b for _, b in sent)


def test_dry_run_nie_zapisuje(env):
    sent, tmp = env
    gm.run(RunOptions(dry_run=True))
    from monitor.core.db import DB
    db = DB(tmp / "monitor.db")
    assert db.count_seen("garaze") == 0 and db.get_meta("baseline:garaze") is None
    assert sent == []
