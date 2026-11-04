"""Uruchomienie: python -m monitor {garaze|dzialki|test-email} [--dry-run] [--only-source NAZWA] [--probe] [--browser]"""
from __future__ import annotations

import argparse
import logging
import sys

from monitor.core.run import RunOptions


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="monitor", description="Monitor ofert: działki i garaże")
    p.add_argument("module", choices=["garaze", "dzialki", "test-email"])
    p.add_argument("--dry-run", action="store_true", help="podgląd: bez maila i bez zapisu w bazie")
    p.add_argument("--only-source", help="tylko źródła, których nazwa zawiera ten tekst")
    p.add_argument("--probe", action="store_true",
                   help="zapisz surowe strony (i JSON z przeglądarki) do probe/ – do dostrojenia parserów; "
                        "obejmuje też źródła wyłączone")
    p.add_argument("--browser", action="store_true", help="włącz Playwright dla źródeł z render: browser")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if a.module == "test-email":
        from monitor.core.mail import send_mail  # noqa: PLC0415
        send_mail("Monitor ofert: test e-mail", "<p>Działa. Sekrety Gmaila są ustawione poprawnie.</p>")
        print("Wysłano mail testowy.")
        return 0

    opts = RunOptions(dry_run=a.dry_run or a.probe, only_source=a.only_source, probe=a.probe)
    browser = None
    if a.browser:
        from monitor.core.browser import Browser  # noqa: PLC0415
        browser = Browser()
    try:
        if a.module == "garaze":
            from monitor.garaze.module import run  # noqa: PLC0415
        else:
            from monitor.dzialki.module import run  # noqa: PLC0415
        result = run(opts, browser)
    finally:
        if browser:
            browser.close()
    # przebieg kończy się sukcesem nawet przy awariach części źródeł; błąd tylko, gdy nie działa nic
    return 1 if result.statuses and len(result.failed) == len(result.statuses) else 0


if __name__ == "__main__":
    sys.exit(main())
