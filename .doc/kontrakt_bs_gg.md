# Vertrag Book Studio ↔ GrammarGraph

Stand 24.09.2026 (Konsolidierungsplan Paket 5). Gleicher Text in beiden Repos:
BS `.doc/kontrakt_bs_gg.md`, GG `.docs/kontrakt_bs_gg.md`.

**Maschinenlesbar und maßgeblich:** `tests/kontrakt/bs_gg_kontrakt.json`.
Der Ordner `tests/kontrakt/` ist in beiden Repos byte-gleich (Vertrag,
Prüfer `pruefe.py`, Beispiel-Lieferung). Die Datei nennt je Kanal, was die
**lesende** Seite braucht, samt Typ; `?` heißt „darf fehlen“.

## Kanäle

| Kanal | Richtung | Erzeuger | Leser |
|---|---|---|---|
| Lieferung (`publish_meta.json`, `_book_studio.toml`, Buch-Markdown) | GG → BS | GG `src/book_delivery.py::liefere` | BS `delivery_intake`, `production_uuid`, `provenance/ingest`, `gg_content_swap`, `uuid_manager`, `import_helpers` |
| Geplante UUIDs (Liste) | BS → GG | BS `planned_uuid.list_planned_cover_uuids` | GG `book_studio_bridge/production_uuid.geplante_uuids` |
| UUID anlegen | GG → BS → GG | BS `create_planned_cover_uuid` | GG `lege_geplante_uuid_an` |
| Übernahme-Nachweis (`books/<Buch>/bookconfig/book_run.json`, `artifacts.delivery`) | BS → GG | BS `accept_delivery` | GG `bisherige_uuids` |
| Layout-Klassen (`tools/doclayout/library/_available_classes.json`) | BS → GG | BS `doclayout/registry.build_registry` | GG `book_studio_bridge/layout_classes` |
| Buchnotiz (`<Buch>/bookconfig/notiz.md`) | beide | beide | beide |

Lieferordner: `<inbox>/<Projekt>/<TT.MM.JJJJ_HH.MM>`. Erkannt wird er an
`publish_meta.json` oder `_book_studio.toml`.

GG ruft BS für die UUIDs als Unterprozess auf (BS-Python im BS-Verzeichnis).
Für Tests lassen sich Registry und Cover-Ablage umlenken:
`BSU_COVER_REGISTRY`, `BSU_COVERS_ROOT`.

## Production-UUID am Buch

- **SSOT ist Book Studio.** Geplante UUIDs entstehen dort (Cover zuerst). GG
  wählt eine davon und erfindet nie eine eigene.
- **Lesen** (BS `read_book_uuid`), in dieser Reihenfolge: `publish_meta.json`
  `uuid` → `bookconfig/grammargraph_export.json` → `_book_studio.toml`
  `[book]`/`[metadata]` `uuid`.
- **Schreiben** (BS `write_book_uuid`, aufgerufen von der Cover-Bindung): nur
  nach `_book_studio.toml` `[book] uuid`, und nur, wenn das Buch noch keine
  UUID trägt. Überschrieben wird nie. Trägt das Buch eine *andere* UUID als das
  Cover, wird nicht gebunden (`conflict`).
- `publish_meta.json` bleibt die unveränderte Lieferquittung von GG.

## Wie der Vertrag geprüft wird

- **GG** (`tests/test_kontrakt_bs_gg.py`) erzeugt mit `liefere()` eine echte
  Lieferung und prüft sie gegen den Vertrag. Weicht die Beispiel-Lieferung
  davon ab, wird der Test rot. Außerdem ruft GG BS live auf (UUID anlegen und
  auflisten, in eine umgelenkte Registry) und liest `book_run.json` und
  `_available_classes.json` in der Vertragsform.
- **BS** (`tests/test_kontrakt_bs_gg.py`) übernimmt die Beispiel-Lieferung mit
  den echten Lesern bis zur Cover-Bindung und prüft, dass geplante UUIDs,
  `book_run.json` und Layout-Klassen in Vertragsform entstehen.
- **Beide** vergleichen `tests/kontrakt/` mit dem Nachbar-Repo (Pfad per
  `KONTRAKT_BS_REPO`/`KONTRAKT_GG_REPO`, sonst der Nachbarordner). Fehlt das
  Nachbar-Repo, werden diese Tests übersprungen.

**Den Vertrag ändern:** zuerst die JSON-Datei anpassen, dann die Seite, die
schreibt. Ändert sich die Lieferung, erzeugt
`KONTRAKT_NEU=1 pytest tests/test_kontrakt_bs_gg.py` in GG die
Beispiel-Lieferung neu. Danach `tests/kontrakt/` ins andere Repo kopieren.
Beide Suiten müssen grün sein.

## Befund beim Einführen (Paket 5)

GGs `tomllib_dumps` escapte nichts. Jeder Windows-Pfad (`source_manifest`)
machte `_book_studio.toml` zu ungültigem TOML (`\U` ist dort ein
Unicode-Escape), und BS verwarf die ganze Datei still. Das ist behoben
(GG 31.63.0). Lieferungen von vorher enthalten die kaputte Datei weiterhin.
`write_book_uuid` lässt sie unangetastet und meldet das.
