"""Pamięć monitora w SQLite (data/monitor.db, commitowana przez bota Actions)."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (module TEXT, key TEXT, first_seen REAL, data TEXT,
                                 PRIMARY KEY (module, key));
CREATE TABLE IF NOT EXISTS fingerprints (module TEXT, fp TEXT, key TEXT, PRIMARY KEY (module, fp));
CREATE TABLE IF NOT EXISTS visited (url TEXT PRIMARY KEY, ts REAL);
CREATE TABLE IF NOT EXISTS failures (module TEXT, source TEXT, count INTEGER, alerted INTEGER,
                                     last_error TEXT, last_ok REAL, PRIMARY KEY (module, source));
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS geocode (q TEXT PRIMARY KEY, lat REAL, lon REAL, ts REAL);
"""


class DB:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path)
        self.con.executescript(SCHEMA)

    # --- oferty / trafienia -------------------------------------------------
    def is_seen(self, module: str, key: str) -> bool:
        return self.con.execute("SELECT 1 FROM seen WHERE module=? AND key=?", (module, key)).fetchone() is not None

    def mark_seen(self, module: str, key: str, data: dict | None = None):
        self.con.execute("INSERT OR IGNORE INTO seen VALUES (?,?,?,?)",
                         (module, key, time.time(), json.dumps(data or {}, ensure_ascii=False)))

    def fp_owner(self, module: str, fp: str) -> str | None:
        r = self.con.execute("SELECT key FROM fingerprints WHERE module=? AND fp=?", (module, fp)).fetchone()
        return r[0] if r else None

    def add_fp(self, module: str, fp: str, key: str):
        self.con.execute("INSERT OR IGNORE INTO fingerprints VALUES (?,?,?)", (module, fp, key))

    def count_seen(self, module: str) -> int:
        return self.con.execute("SELECT COUNT(*) FROM seen WHERE module=?", (module,)).fetchone()[0]

    # --- odwiedzone podstrony (głębokie sprawdzanie garaży) ---------------
    def visited_recently(self, url: str, days: int) -> bool:
        r = self.con.execute("SELECT ts FROM visited WHERE url=?", (url,)).fetchone()
        return bool(r) and time.time() - r[0] < days * 86400

    def mark_visited(self, url: str):
        self.con.execute("INSERT OR REPLACE INTO visited VALUES (?,?)", (url, time.time()))

    def prune_visited(self, days: int):
        self.con.execute("DELETE FROM visited WHERE ts < ?", (time.time() - days * 86400,))

    # --- awarie źródeł ------------------------------------------------------
    def record_failure(self, module: str, source: str, error: str) -> int:
        self.con.execute(
            "INSERT INTO failures VALUES (?,?,1,0,?,NULL) ON CONFLICT(module, source) "
            "DO UPDATE SET count=count+1, last_error=excluded.last_error", (module, source, error[:500]))
        return self.con.execute("SELECT count FROM failures WHERE module=? AND source=?",
                                (module, source)).fetchone()[0]

    def record_ok(self, module: str, source: str):
        self.con.execute(
            "INSERT INTO failures VALUES (?,?,0,0,NULL,?) ON CONFLICT(module, source) "
            "DO UPDATE SET count=0, alerted=0, last_ok=excluded.last_ok", (module, source, time.time()))

    def failures_to_alert(self, module: str, threshold: int) -> list[tuple[str, int, str]]:
        return self.con.execute(
            "SELECT source, count, last_error FROM failures WHERE module=? AND count>=? AND alerted=0",
            (module, threshold)).fetchall()

    def mark_alerted(self, module: str, sources: list[str]):
        self.con.executemany("UPDATE failures SET alerted=1 WHERE module=? AND source=?",
                             [(module, s) for s in sources])

    # --- różne ------------------------------------------------------------
    def get_meta(self, k: str) -> str | None:
        r = self.con.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return r[0] if r else None

    def set_meta(self, k: str, v: str):
        self.con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, v))

    def get_geocode(self, q: str):
        r = self.con.execute("SELECT lat, lon FROM geocode WHERE q=?", (q,)).fetchone()
        return r if r else None

    def put_geocode(self, q: str, lat: float | None, lon: float | None):
        self.con.execute("INSERT OR REPLACE INTO geocode VALUES (?,?,?,?)", (q, lat, lon, time.time()))

    def commit(self):
        self.con.commit()

    def rollback(self):
        self.con.rollback()

    def close(self):
        self.con.close()
