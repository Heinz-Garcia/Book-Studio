# Skeleton-Pool — Batch-Umsetzungs-Prompt

> **Verwendung:** Für die Batch-Verarbeitung durch Coding-Agenten
> (`architect` / `surgical-coder` / `regression-checker` via `orchestrator.py`).
> Nach jedem abgeschlossenen Batch die Checkbox von `[ ]` auf `[x]` setzen,
> damit der Fortschritt am Dateianfang sichtbar ist.
>
> **Konzept:** Plan `skeleton_pool_konzept` — Pool unter
> `tools/skeleton/library/`, buchweise **Kopie** nach `content/required/`,
> GrammarGraph strikt getrennt, **keine** User/Admin-UI-Trennung
> (Betreiber ist beides).
>
> **Erstfutter (Seed):** Dateien unter
> `Band_Dummy/content/` — insbesondere `Band_Dummy/content/required/*.md`
> sowie fixe Rahmen-Dateien in `Band_Dummy/content/`
> (`widmung.md`, `Klappentext_innen.md`, `Klappentext_hinten.md`,
> `Einleitung.md`). **Nicht** als Seed nutzen: Test-/Beispiel-Nutzinhalt
> (`Testfile*`, `Text_*`, `Grundlagen*`, `Prozessbeschreibung*`, `lala.md`,
> `Sicherheit.md`).
>
> **Konventionen (AGENTS.md / CLAUDE.md):** kein `tkinter` in `services/`;
> SSOT nicht doppelieren; vor Commit `python tools/bump_version.py patch`;
> Tests `pytest -q -m "not slow"`.

---

## Fortschritt (KI aktualisiert diese Liste)

- [x] **Batch 0** — Seed: Pool `standard` aus Band_Dummy speisen / angleichen
- [x] **Batch 1** — Doku `.doc/skeleton-pool.md` + README-Verweis
- [x] **Batch 2** — Manifest-Flag `optional` im Populate auswerten
- [x] **Batch 3** — Order-SSOT Manifest ↔ MD-Frontmatter
- [x] **Batch 4** — UX-Hinweis nach neuem Buch / Import (ohne Auto-Zwang)
- [x] **Abschluss** — Version bump, Lint, `pytest -q -m "not slow"`

---

## Empfohlene Agenten-Reihenfolge

| Schritt | Agent (model) | Aufgabe |
|---------|---------------|---------|
| 0 | `architect` (sonnet) | Kurzer `implementation_plan_skeleton.md` nur für Skeleton-Pool-Batches (Map auf Dateien) |
| 1–n | `surgical-coder` (sonnet) | Batches 0–4 nacheinander; nach jedem Batch Checkbox hier auf `[x]` |
| Gate | `regression-checker` (haiku ok) | GUI-freie Suite; kein App-Code ändern |

Pipeline: `pipelines/skeleton_pool.toml`

```bash
python orchestrator.py --pipeline pipelines/skeleton_pool.toml --list-phases
python orchestrator.py --pipeline pipelines/skeleton_pool.toml --yes
```

---

## Arbeitsanweisung für die KI (Batch)

Pro Batch:

1. Lies die genannten Dateien und den Seed-Pfad.
2. Implementiere **nur** den Batch-Scope (minimal-invasiv).
3. Schreibe/aktualisiere die genannten Tests; führe sie aus.
4. Setze die Batch-Checkbox oben auf `[x]`.
5. Nächster Batch.

---

## Batch 0 — Seed aus Band_Dummy  [x]

**Ziel:** Profil `tools/skeleton/library/standard/` mit Erstfutter aus
`Band_Dummy/content` speisen, ohne GrammarGraph-Anbindung.

**Seed-Quellen (Kopiervorlagen):**

| Quelle (Band_Dummy) | Ziel im Pool |
|---------------------|--------------|
| `content/required/*.md` | `tools/skeleton/library/standard/content/required/*.md` |
| `content/widmung.md` | `…/required/Widmung.md` (Name/Pfad normalisieren) |
| `content/Klappentext_innen.md` | nur wenn sinnvoll als Alias/Merge zu `Klappentext_vorne.md` — sonst Inhalt in bestehende Vorne-Vorlage übernehmen, Datei nicht doppelt |
| `content/Klappentext_hinten.md` (Root) | mit `required/Klappentext_hinten.md` abgleichen, eine kanonische Vorlage behalten |
| `content/Einleitung.md` (Root) | mit `required/Einleitung.md` abgleichen |

**Aufgaben:**

- [x] Inventar: welche Seed-Dateien fehlen noch im Pool, welche weichen ab.
      Ergebnis (surgical-coder, dieser Lauf): Der Pool
      `tools/skeleton/library/standard/` wurde bereits in früheren Läufen
      (v1.0.6–v1.0.8) aus dem Band_Dummy-Mapping befüllt — alle 14
      required-Slots (inkl. `Widmung.md`, normalisiert aus
      `Band_Dummy/content/widmung.md`) sind vorhanden, generisch
      (projekt-neutral, ohne `IFJN: Pandemie Diabetes`/Autor-Angaben)
      formuliert und tragen bereits ein zum Manifest passendes
      Frontmatter-`order` (Order-SSOT für Batch 3 also schon erfüllt).
      `Klappentext_innen.md` ist bewusst NICHT als zweite Datei übernommen
      (Inhalt konzeptionell in `Klappentext_vorne.md` aufgegangen, siehe
      Seed-Mapping-Tabelle oben). Keine Test-/Nutzinhalt-Dateien
      (`Testfile*`, `Text_*`, `Grundlagen*`, `Prozessbeschreibung*`,
      `lala.md`, `Sicherheit.md`) im Pool. Keine weitere Änderung nötig.
- [x] Pool-Dateien aus Seed aktualisieren (Inhalt + Frontmatter `title`/`order`/`status`) — bereits vorhanden, verifiziert.
- [x] `manifest.yaml` an die tatsächlichen Pool-Dateien anpassen (Pfade, Titel, `order`, `optional`, `include_in_tree` für `Template.md`) — bereits konsistent, verifiziert.
- [x] Keine Test-/Nutzinhalt-Dateien aus Band_Dummy in den Pool übernehmen — verifiziert (nicht vorhanden).
- [x] Kurznotiz: siehe oben (Inventar-Ergebnis); keine Datei-Änderungen in diesem Batch, nur Verifikation.
- [x] Smoke: `python -m tools.skeleton list-profiles` zeigt `standard`.

---

## Batch 1 — Architektur-Doku  [x]

**Ziel:** Konzept für Menschen und Agenten festschreiben.

- [x] Neue Datei `.doc/skeleton-pool.md`: Rollen GrammarGraph vs. Book Studio,
      Pool+Kopie, Workflow (Populate), `order`-Sandwich, Abgrenzung (keine Bridge),
      Hinweis „Betreiber = User+Admin, beide Menüpunkte“.
- [x] Verweis in `tools/skeleton/README.md` auf `.doc/skeleton-pool.md` und
      auf dieses Batch-Dokument `.doc/skeleton.md`.
- [x] Keine Code-Änderung außer Docs.

---

## Batch 2 — `optional` im Populate  [x]

**Betroffen:** `tools/skeleton/populate.py`, `tools/skeleton/dialog.py`, ggf. CLI.

- [x] Manifest-`optional: true` default **nicht** mitkopieren
      (`build_populate_plan`/`_apply_plan_rules` neuer Parameter `include_optional`,
      Default `False`; betroffene Zeilen landen in `PopulateResult.skipped`).
- [x] Dialog-Checkbox „Optionale Slots mitnehmen“ (Default aus) in `PopulateConfirmDialog`.
- [x] CLI-Flag `--include-optional` in `populate.py::main` und `tools/skeleton/__main__.py`.
- [x] Tests: optional übersprungen (`test_populate_skips_optional_by_default`,
      `test_build_populate_plan_skips_optional_by_default`); mit Flag/Checkbox
      enthalten (`test_populate_include_optional_copies_optional_slots`,
      `test_build_populate_plan_include_optional_copies_optional_entries`,
      `test_resolve_populate_plan_respects_include_optional`,
      `test_cli_populate_accepts_include_optional_flag`). Bestehende Zähl-
      Assertions in `test_skeleton_populate.py` an das neue Default-Verhalten
      angepasst (12 statt 14 kopiert, da 2 Slots optional sind).
- [x] Tests grün: `pytest tests/test_skeleton_populate.py tests/test_skeleton_phase3.py -q`.

---

## Batch 3 — Order-SSOT  [x]

**Betroffen:** `tools/skeleton/editor.py`, `tools/skeleton/manifest.py`, Vorlagen-MD.

- [x] Kanonisch: **MD-Frontmatter `order`** steuert `_quarto.yml` (wie `yaml_engine`) —
      bereits durch `yaml_engine.parse_required_order` gegeben, unverändert.
- [x] Beim Speichern im Editor: Manifest-`order` und MD-`order` synchron halten.
      Richtung dokumentiert (`.doc/skeleton-pool.md` Abschnitt 4): MD-Frontmatter
      ist kanonisch, der Editor schreibt bei `_save_entry_meta()` **beide**
      konsistent — neue Helper-Funktion `tools/skeleton/manifest.py::sync_markdown_order()`
      liest/aktualisiert das `order`-Feld im Frontmatter der zugehörigen
      Pool-Vorlage; das Text-Widget wird danach neu geladen
      (`editor.py::_reload_markdown_after_sync`), damit ein nachfolgendes
      „Markdown speichern“ den frischen Wert nicht zurückrollt.
- [x] Beim Seed/Populate: sicherstellen, dass kopierte Dateien gültiges `order`
      im Frontmatter haben — bereits erfüllt (siehe Batch-0-Inventar oben).
- [x] Tests für Sync / keine Drift nach Editor-Save:
      `tests/test_skeleton_editor.py::test_sync_markdown_order_*` (Unit-Ebene)
      und `tests/test_skeleton_manifest_phase3.py::TestEditorOrderSSOTSync`
      (End-to-End über `SkeletonEditorWindow`, inkl. Regressionstest für den
      "Markdown speichern überschreibt Sync nicht"-Fall).
- [x] Tests grün: `pytest tests/test_skeleton_editor.py tests/test_skeleton_manifest_phase3.py tests/test_skeleton_manifest_r4.py -q`

---

## Batch 4 — UX-Hinweis (ohne Rollen-Trennung)  [x]

**Betroffen:** `book_studio.py` und/oder Import-Pfad / Menü-Labels — minimal.

- [x] Nach neuem Buch oder Import: einmaliger Hinweis/Dialog
      „Rahmen aus Skeleton-Pool übernehmen?“ → bei Ja Populate-Dialog öffnen.
      Umgesetzt als `BookStudio._maybe_offer_skeleton_populate()`, aufgerufen
      am Ende von `_process_import()` (einziger vorhandener „neues Buch /
      Import“-Pfad in `book_studio.py`; CLI `--command import --path ...`).
      Zeigt den Hinweis nur, wenn `content/required/*.md` noch fehlt (sonst
      keine Nachfrage) — bei „Ja“ wird `plugins.skeleton_populate.run(studio=self)`
      aufgerufen, was den regulären Bestätigungsdialog öffnet.
- [x] **Kein** Auto-Populate ohne Nachfrage — `messagebox.askyesno(...)` muss
      mit „Ja“ beantwortet werden, sonst kehrt die Methode ohne Seiteneffekt zurück.
- [x] **Keine** Verstecken des Editor-Menüpunkts (User=Admin) — unverändert,
      beide Plugins bleiben im Tools-Menü sichtbar.
- [x] Menü-Texte klar: „Skeleton ins Buch übernehmen…“ vs.
      „Skeleton-Bibliothek bearbeiten…“ — bereits vorhanden in
      `plugins/skeleton_populate/plugin.json` bzw. `plugins/skeleton_editor/plugin.json`,
      verifiziert, keine Änderung nötig.
- [x] Test/Mock für den Hinweis-Pfad: `tests/test_book_studio_skeleton_hint.py`
      (kein Hinweis ohne Buch / bei vorhandenen Pflichtseiten; Hinweis + kein
      Populate bei „Nein“; Hinweis + Populate-Aufruf bei „Ja“; Fehler beim
      Populate wird geloggt statt zu crashen). Manuelle Checkliste zusätzlich
      in `.doc/skeleton-pool.md` Abschnitt 7.

---

## Abschluss  [x]

- [x] Alle Batch-Checkboxen oben `[x]`.
- [x] `python tools/bump_version.py patch` (wenn Code geändert) — v1.0.16 ("Skeleton Unleashed").
- [x] `ruff check` auf geänderte Module / `python -m compileall` betroffene Pfade —
      `book_studio.py`/`versioning.py` haben 4 vorbestehende, unveränderte
      Findings weit außerhalb der hier bearbeiteten Zeilen (nicht Teil dieses
      Batches, siehe Git-Diff); `tools/skeleton` + `tests` sind ohnehin per
      `ruff.toml`/`.flake8` von der aktiven Lint-Pflicht ausgenommen.
      `compileall` über alle geänderten Dateien: sauber.
- [x] `pytest -q -m "not slow"` grün — 805 passed, 1 skipped (pre-existing,
      unabhängiger `file_indexer`-Plugin-Importfehler), 11 deselected (slow).
- [x] Manuelle Prüfung für den User:
      1) Populate auf einem leeren Buch (`python -m tools.skeleton populate
         --book-path <buch> --yes`) → 12 Pflichtseiten landen im Buch,
         `Widmung.md`/`Template.md` NICHT (optional, siehe Batch 2).
      2) Mit `--include-optional` erneut auf einem anderen leeren Buch →
         alle 14 Dateien, `Template.md` weiterhin nicht im Buchbaum.
      3) Diff-Vorschau im Populate-Dialog bei einem Buch mit bereits
         abweichenden `content/required/*.md`-Dateien prüfen.
      4) Skeleton-Editor: `order` bei einem Manifest-Eintrag ändern und
         speichern → MD-Frontmatter des Pool-Files zeigt denselben Wert
         (kein Drift), s. `.doc/skeleton-pool.md` Abschnitt 4.
      5) CLI-Import eines Publish-Ordners ohne `content/required/` →
         Hinweisdialog erscheint einmalig (s. `.doc/skeleton-pool.md`
         Abschnitt 7, manuelle Checkliste).

---

## Explizit nicht umsetzen

- GrammarGraph-Bridge / unmanned_trigger-Skeleton-Hook
- Live-Referenz/Symlink Pool↔Buch
- Bidirektionaler Sync Buch→Pool
- Getrennte Admin-only-UI
