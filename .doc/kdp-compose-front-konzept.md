# Vorderseiten-Compositor (Experiment, wegwerfbar)

## Zielbild

Über dem Front-Foto, Z-Order von unten nach oben:

1. Foto (bestehendes cover-fit)
2. Fade (heller Verlauf von oben)
3. Band (Rechteck; komplexe Schleife nur als PNG)
4. Titelzeilen (Reihe / Haupt / Akzent)
5. Fußzeile (optional)
6. Badge/Stempel (PNG und/oder schräger Text)

Kein Amazon-ZIP — alles lokal im Studio.

## Isolation

| Baustein | Ort |
|----------|-----|
| Package | `tools/kdp_cover/compose_front/` |
| Hook | `export_pdf.render_wrap_image` nach Front-Paste |
| Daten | `CoverLayout.front_compose` + Flag `enabled` |
| UI | Gruppe „Vorderseite gestalten (Experiment)“ |

`ImportError` oder `enabled=false` → Pipeline wie ohne Modul.

## Wegwerf-Checkliste

1. Ordner `tools/kdp_cover/compose_front/` löschen
2. Hook-Block in `export_pdf.py` entfernen
3. Dialog-Gruppe + `_collect`/`_apply`/`_wire` Compose-Methoden entfernen
4. Optionales Feld `front_compose` in Layout-JSON ignorieren (unkritisch)

Maße, Validierung, Kanal-Flag und Speichern bleiben unberührt.

## Persistenz

Weiterhin `{Buch}_kdp_cover.json` unter `export/kdp_cover/`. Nested-Key `front_compose`.

**Elementset** (nur Layer): `{Buchtitel}_elementset.json` — speichern/laden unabhängig vom Cover-Layout,
damit Elemente in einem anderen Buch weitereditierbar übernommen werden können.
