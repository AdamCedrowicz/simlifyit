"""Wspólny przebieg modułu: punkt wyjścia, oznaczanie „widzianych” po udanym mailu, alerty o awariach."""
from __future__ import annotations

import html
import logging
import os
from dataclasses import dataclass, field

from monitor.core.db import DB
from monitor.core.mail import send_mail

log = logging.getLogger("monitor")


@dataclass
class RunOptions:
    dry_run: bool = False
    only_source: str | None = None
    probe: bool = False


@dataclass
class SourceStatus:
    name: str
    ok: bool
    count: int = 0
    error: str = ""


@dataclass
class RunResult:
    statuses: list[SourceStatus] = field(default_factory=list)

    def add(self, st: SourceStatus):
        self.statuses.append(st)
        lvl = logging.INFO if st.ok else logging.WARNING
        log.log(lvl, "%-45s %s %s", st.name[:45], "OK " if st.ok else "BŁĄD", st.count if st.ok else st.error[:150])

    @property
    def failed(self) -> list[SourceStatus]:
        return [s for s in self.statuses if not s.ok]


def track_source(db: DB, module: str, st: SourceStatus, dry_run: bool):
    if dry_run:
        return
    if st.ok:
        db.record_ok(module, st.name)
    else:
        db.record_failure(module, st.name, st.error)


def deliver(db: DB, module: str, new_items: list[tuple[str, dict]], subject: str, body_html: str,
            opts: RunOptions, startup_mail: bool = False) -> str:
    """Wysyła maila i dopiero potem zapisuje pozycje jako widziane. Zwraca opis tego, co się stało."""
    baseline_key = f"baseline:{module}"
    first_run = db.get_meta(baseline_key) is None
    if opts.dry_run:
        return f"dry-run: {len(new_items)} nowych (bez maila i bez zapisu)"
    if first_run and not opts.only_source:
        if startup_mail and new_items:
            send_mail(f"[start] {subject}", body_html)
        for key, data in new_items:
            db.mark_seen(module, key, data)
        db.set_meta(baseline_key, "1")
        db.commit()
        return f"pierwszy przebieg: punkt wyjścia z {len(new_items)} pozycji"
    if not new_items:
        db.commit()
        return "brak nowości"
    send_mail(subject, body_html)  # błąd = wyjątek: nic nie oznaczamy, ponowienie w kolejnym przebiegu
    for key, data in new_items:
        db.mark_seen(module, key, data)
    db.commit()
    return f"wysłano mail: {len(new_items)} nowych"


def alert_failures(db: DB, module: str, threshold: int, opts: RunOptions, urls: dict[str, str]):
    if opts.dry_run:
        return
    rows = db.failures_to_alert(module, threshold)
    if not rows:
        return
    items = "".join(
        f"<li><b>{html.escape(src)}</b> ({cnt} błędów z rzędu)<br>"
        f"<a href='{html.escape(urls.get(src, ''))}'>{html.escape(urls.get(src, ''))}</a><br>"
        f"<small>{html.escape(err or '')}</small></li>" for src, cnt, err in rows)
    send_mail(f"Monitor ({module}): {len(rows)} źródeł nie działa – sprawdź adresy",
              f"<p>Te źródła nie odpowiadają od kilku przebiegów. Sprawdź, czy adres się nie zmienił.</p><ul>{items}</ul>")
    db.mark_alerted(module, [r[0] for r in rows])
    db.commit()


def write_summary(title: str, result: RunResult, outcome: str):
    """Podsumowanie w zakładce Actions (GITHUB_STEP_SUMMARY)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    lines = [f"## {title}", "", f"**Wynik:** {outcome}", "",
             f"Źródła: {len(result.statuses)}, działa: {len(result.statuses) - len(result.failed)}, "
             f"błędy: {len(result.failed)}", "", "| Źródło | Stan | Wynik |", "|---|---|---|"]
    for s in result.statuses:
        lines.append(f"| {s.name} | {'OK' if s.ok else 'BŁĄD'} | "
                     f"{s.count if s.ok else s.error[:120].replace('|', '/')} |")
    text = "\n".join(lines) + "\n"
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
