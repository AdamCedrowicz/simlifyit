# Monitor ofert: działki i garaże

Codzienny automat w GitHub Actions: przegląda licytacje komornicze, KAS, Adradar, Otodom, OLX i strony urzędów,
a gdy pojawi się coś nowego, wysyła e-mail. Osobne maile dla działek (6:30) i garaży (8:00 i 18:00).

## Stan prac

| Etap | Stan |
|---|---|
| 1. Szkielet: HTTP, baza SQLite, Gmail, `--test-email`, workflow | gotowe |
| 2. Garaże: logika z `monitor-garazy.ps1` (3 sposoby wykrywania, reguły słów, test bliskości, pamięć podstron, alerty) | gotowe; **brak listy 109 stron** (patrz niżej) |
| 3. Działki – licytacje: komornik, KAS, Adradar (+ KRZ do ręcznego przeglądu); odsiew, deduplikacja, raport | kod gotowy; **wzorce stron do dostrojenia po pierwszym `probe`** |
| 4. Działki – ULDK, ha przeliczeniowe, zł/ha przel., flagi, ocena | gotowe (okręgi podatkowe do uzupełnienia) |
| 5. Otodom, OLX | wstępnie; KOWR i BIP-y gmin/starostw – do zrobienia |
| 6. KAS i komornik dla garaży | do zrobienia |

Parserów nie dało się sprawdzić na żywo: sesja, w której powstał kod, nie miała dostępu do tych portali.
Dlatego jest tryb **probe**: zapisuje surowe strony (i JSON-y z wewnętrznych API stron w JavaScripcie)
do artefaktu w Actions, a na ich podstawie poprawia się wzorce w `config/zrodla_dzialki.yaml`.

## Uruchomienie krok po kroku

### 1. Prywatne repozytorium
Ten katalog powinien być **osobnym, prywatnym** repozytorium (baza z ofertami i ustawienia nie powinny być publiczne).

1. GitHub → **New repository** → nazwa `monitor-ofert` → zaznacz **Private** → *Create repository*.
2. Skopiuj zawartość katalogu `monitor-ofert/` (razem z ukrytym `.github/`) do nowego repozytorium.
   Najprościej poprosić o to Claude Code w sesji z dostępem do nowego repozytorium.

Workflow uruchamiają się tylko wtedy, gdy `.github/workflows/` leży w głównym katalogu repozytorium.

### 2. Hasło aplikacji Google
1. Wejdź na <https://myaccount.google.com/security> i włącz **weryfikację dwuetapową** (bez niej hasła aplikacji są niedostępne).
2. Wejdź na <https://myaccount.google.com/apppasswords>, wpisz nazwę np. „monitor-ofert”, kliknij *Utwórz*.
3. Skopiuj 16-znakowe hasło. **Nie wklejaj go w czacie ani do plików** – tylko do sekretów (krok 3).

### 3. Sekrety w GitHubie
Repozytorium → **Settings → Secrets and variables → Actions → New repository secret**. Dodaj:

| Nazwa | Wartość |
|---|---|
| `GMAIL_USER` | adres Gmail, z którego idą maile |
| `GMAIL_APP_PASSWORD` | hasło aplikacji z kroku 2 |
| `MAIL_TO` | adres odbiorcy (może być ten sam) |
| `REF_PARCEL_ID` | identyfikator działki w Jackowie (np. `240408_2.0003.xxxx`): z niego liczony jest środek okręgu 35 km |

### 4. Lista stron garaży
Wklej zawartość `strony.json` z monitora PowerShell (109 stron) do `config/strony_garaze.json`
(format bez zmian: `name, city, type, url, enabled, note`). Stronom wymagającym JavaScriptu można dopisać `"render": "browser"`.

### 5. Pierwsze uruchomienia (zakładka **Actions**)
1. **Działki → Run workflow → tryb `test-email`** – powinien przyjść mail testowy.
2. **Garaże → `dry-run`** – w podsumowaniu przebiegu tabela: które strony działają z serwerów GitHuba, które nie.
   Porównaj liczbę trafień z testem z 15.10.2026 (34 trafienia).
3. **Działki → `probe`** – pobierz artefakt `probe-dzialki` i daj go Claude Code do dostrojenia parserów.
4. Gdy wyniki wyglądają dobrze: **`normal`**. Pierwszy normalny przebieg tworzy punkt wyjścia (bez maila o nowościach),
   kolejne wysyłają tylko nowości. Potem działa już harmonogram.
5. Jeśli w Harmonogramie zadań Windows włączone jest zadanie „Monitor garazy Katowice” – wyłącz je (podwójne maile).

Ustaw w GitHubie **Settings → Billing → Spending limit = 0 $**. Szacunkowe zużycie: ok. 350–450 min/mies.
(każdy wpis harmonogramu poza właściwą godziną kończy się po kilku sekundach, ale GitHub liczy go jako 1 minutę).

## Tryby (lokalnie lub w Actions)

```bash
pip install -r requirements.txt            # + requirements-browser.txt i `python -m playwright install chromium`
python -m monitor test-email
python -m monitor garaze --dry-run          # podgląd: bez maila i bez zapisu
python -m monitor dzialki --browser --dry-run --only-source komornik
python -m monitor dzialki --browser --probe # surowe strony do katalogu probe/
python -m pytest -q
```

## Jak to działa

- **Każde źródło osobno**: błąd jednego nie zatrzymuje reszty. Po 6 błędach z rzędu przychodzi jeden mail z prośbą o sprawdzenie adresu.
- **„Widziane” dopiero po wysłaniu maila**: gdy wysyłka się nie uda, nowości wrócą w kolejnym przebiegu.
- **Działki odrzucane od razu tylko gdy**: udział ułamkowy (ale „udział w drodze dojazdowej” nie) albo odległość > 35 km.
  Wszystko inne zostaje z flagami i oceną. Przy lokalizacji znanej tylko z poziomu powiatu oferta nie jest odrzucana.
- **Identyfikacja działki (ULDK)**: identyfikator w treści → `GetParcelById`; współrzędne z ogłoszenia → siatka `GetParcelByXY`
  (po 8 zapytań równolegle) i dopasowanie po powierzchni; w raporcie link do Geoportalu albo kandydaci z pewnością dopasowania.
- **zł / ha przeliczeniowy**: użytki i klasy z opisu (np. „RIVa 0,5 ha”), przeliczniki z art. 4 ustawy o podatku rolnym
  (`monitor/dzialki/przeliczniki.py` – tabelę zweryfikować z aktualnym tekstem). Okręg podatkowy gminy z `config/okregi_podatkowe.yaml`;
  dopóki gminy tam nie ma, raport pisze „okręg III (założony)”.
- **Deduplikacja między źródłami**: po sygnaturze (Km …), identyfikatorze działki albo miejscowość + powierzchnia + cena.
- **Bez obchodzenia zabezpieczeń**: bez logowania, CAPTCHA i paywalli. Zablokowane źródło trafia do sekcji „do ręcznego przeglądu”.

## Konto w eLicytacjach KAS
**Nie jest potrzebne i lepiej go nie dodawać.** Ogłoszenia KAS można przeglądać bez logowania, a monitor tylko czyta listy.
Konto przydaje się dopiero do udziału w licytacji – wtedy zakładasz je i licytujesz ręcznie. Login do konta w sekretach
oznaczałby niepotrzebne ryzyko, gdyby repozytorium lub workflow kiedyś wyciekły.

## Zastrzeżenia
Monitor wskazuje okazje, ale nie zastępuje sprawdzenia księgi wieczystej, operatu, dojazdu i stanu prawnego.
Portale ogłoszeniowe ograniczają automatyczne pobieranie w regulaminach: niska częstotliwość, tylko na własny użytek.
