# Zasady pracy w tym repozytorium (dla Claude Code)

Użytkownik pisze po polsku – odpowiadaj po polsku, prosto i konkretnie. Kontekst projektu: `README.md`.

## Bezpieczeństwo
- Nigdy nie proś o hasła w czacie i nie zapisuj sekretów w plikach. Sekrety tylko w GitHub Secrets.
- Nie obchodzimy zabezpieczeń stron: bez logowania na cudze konta, łamania CAPTCHA i omijania paywalli.

## Sposób pracy (Karpathy guidelines + superpowers)
1. **Najpierw pomyśl**: nazwij założenia; gdy coś jest niejasne – zapytaj, zamiast zgadywać.
2. **Prostota**: minimum kodu, które rozwiązuje problem. Bez spekulatywnych abstrakcji i opcji „na zapas”.
3. **Zmiany chirurgiczne**: dotykaj tylko tego, czego wymaga zadanie; trzymaj się istniejącego stylu.
4. **Cel weryfikowalny**: najpierw test, który pokazuje problem (czerwony), potem kod (zielony).
   Nowe źródło = test parsera na prawdziwym fragmencie HTML z artefaktu `probe`.
5. **Weryfikacja przed ogłoszeniem sukcesu**: uruchom `python -m pytest -q` i pokaż wynik. Bez „powinno działać”.

## Architektura w skrócie
- `monitor/core/` – HTTP, przeglądarka (Playwright, leniwie), SQLite, mail, wspólny przebieg (`run.py`).
- `monitor/sources/` – źródło = `fetch(cfg, ctx) -> list[Offer]`; wzorce stron w `config/zrodla_dzialki.yaml`.
- `monitor/garaze/` – logika z `monitor-garazy.ps1` (bez zmian zachowania).
- `monitor/dzialki/` – odsiew, ULDK, przeliczniki, ocena, raport.
- Strojenie źródła: workflow w trybie `probe` → artefakt z HTML/JSON → poprawka wzorca + test na fragmencie.
