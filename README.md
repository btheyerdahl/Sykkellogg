# Sykkellogg

Enkel web-app for å holde orden på vedlikeholdet av familiens sykler.
Fase 1: sykkeloversikt, servicelogg og permanent lagring (SQLite).

## Krav

- Python 3.8+ (kun standardbiblioteket — ingen `pip install` nødvendig)

## Start appen

```bash
cd sykkellogg
python3 app.py
```

Åpne deretter <http://localhost:8000> i nettleseren.

Valgfrie flagg:

```bash
python3 app.py --port 8080                 # annen port
python3 app.py --host 0.0.0.0 --port 8000  # nå appen fra mobil på samme WiFi via http://<datamaskinens-ip>:8000
python3 app.py --no-seed                   # start uten eksempeldata
```

Ved første kjøring legges det inn 4 eksempelsykler og noen serviceoppføringer
(slett dem i UI-et, eller kjør med `--no-seed`).

## Hvordan teste manuelt (anbefalt rekkefølge)

1. Start serveren (`python3 app.py`) og åpne <http://localhost:8000>.
2. **Sykler-fanen**: se de 4 eksempelsykler med eier, type og km-stand.
   - Trykk «+ Legg til sykkel», fyll ut eier/type/km, trykk «Lagre».
   - Trykk «Rediger» på en sykkel, endre km-stand, lagre.
   - Trykk «Slett» på en sykkel (bekreft) — og sjekk at tilhørende serviceoppføringer også forsvinner.
3. **Servicelogg-fanen**: trykk «+ Ny service», velg sykkel, komponent, dato (fylt ut med i dag), km ved bytte og en merknad. Lagre.
   - Bruk filteret «Alle sykler / <navn>» for å filtrere på én sykkel.
   - Rediger og slett en oppføring.
4. **Permanent lagring**: lukk nettleserfanen, start serveren på nytt (`Ctrl+C`, så `python3 app.py`), åpne siden igjen — alle data skal være intakte.
5. **Mobilvisning**: sett nettleserens vindu smalt (eller bruk mobil på samme WiFi med `--host 0.0.0.0`) og sjekk at kortene og knappene er enkle å treffe.

## Automatisk test

```bash
cd sykkellogg
python3 test_api.py
```

Starter en lokal server på en tilfeldig port med en midlertidig database og
kjører gjennom hele CRUD-flyten, validering (400/404), statiske filer og
persistens over restart. Skriver `PASS`/`FAIL` per sjekk og avslutter med
non-zero exit-kode hvis noe feiler.

## API-oversikt

| Metode | Endepunkt | Beskrivelse |
|---|---|---|
| GET | `/api/bikes` | Alle sykler, inkl. antall og siste service |
| POST | `/api/bikes` | Ny sykkel `{owner, type, km}` |
| PUT | `/api/bikes/:id` | Oppdater sykkel |
| DELETE | `/api/bikes/:id` | Slett sykkel (serviceoppføringer følger med) |
| GET | `/api/service?bike_id=` | Serviceoppføringer (valgfritt filter), nyeste først |
| POST | `/api/service` | Ny oppføring `{bike_id, component, date, km, note}` |
| PUT | `/api/service/:id` | Oppdater oppføring |
| DELETE | `/api/service/:id` | Slett oppføring |
| GET | `/api/components` | Komponentliste `{key, label, interval_km}` |

Komponenter: `kjede, bremseklosser, dekk, slanger, kassett, kabler, kranklager, hjullager, gaffelservice, skivebremser`.
Datoformat: `ÅÅÅÅ-MM-DD`. Feil svarer med `{"error": "..."}` og passende statuskode.

## Lagring

Alle data ligger i SQLite-filen `data/app.db` (opprettes automatisk).
For å starte helt på nytt: stopp serveren og slett `data/app.db`.

## Arkitektur — klar for fase 2 og 3

- **Fase 2 (slitasjestatus / forfallsliste):** Komponentenheter ligger allerede i
  egen tabell (`components`) med en `interval_km`-kolonne som nå er `NULL`.
  Status kan beregnes server-side (f.eks. `GET /api/status` som sammenligner
  `sykkel.km - sist_km_for_komponent` mot `interval_km`), og intervallene blir
  redigerbare via `PUT /api/components/:key`. Frontend har én `render*`-funksjon
  per fane, så en ny «Status»-fane er et lite tillegg.
- **Fase 3 (PWA/iPhone):** legg til `manifest.webmanifest` og en service worker
  (`sw.js`) i `static/` og referer dem fra `index.html` — serveren betjener
  allerede statiske filer med riktige content-typer (`.webmanifest` er med i
  `CONTENT_TYPES`), så det krever ingen backend-endring.

## Filstruktur

```
sykkellogg/
├── app.py            # HTTP-server, REST-API, statiske filer
├── db.py             # SQLite-skjema, komponenter, eksempeldata
├── test_api.py       # automatisk API-test (python3 test_api.py)
├── static/
│   ├── index.html    # UI (to faner: Sykler / Servicelogg)
│   ├── styles.css    # mobil-først styling
│   └── app.js        # frontend-logikk (api-klient + render per fane)
└── data/app.db       # opprettes ved første kjøring
```
