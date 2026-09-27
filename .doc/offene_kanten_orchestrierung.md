# Offene Kanten — 1-Klick-Orchestrierung (Batch D4)

Stand: 2026-09-26  
Quelle: [1klick-orchestrierung-beide-apps.md](1klick-orchestrierung-beide-apps.md)

Bewusst **nicht** still geschlossen — entweder späterer Slice oder Produktentscheid.

| Kante | Status | Hinweis |
|-------|--------|---------|
| GG schreibt `zone_gg` / Lock bei Handoff nur best-effort über JSON-Marker | offen | BS claimt und setzt Lock; volle GG-Writer-API für `band_run` fehlt noch |
| Handoff → BS ohne laufende GUI (Headless/CI Claim) | erledigt (27.09.) | `python -m tools.automatik lauf --profil <automatik.json>` (siehe [automatik_gg_bis_docx.md](automatik_gg_bis_docx.md)) |
| `band_run` nach Handoff ohne Buch-/Lieferpfad (Lock bs vs. orchestrator) | erledigt (27.09.) | Bridge schreibt als Claimant (`band_run_writer="bs"`) |
| QProcess GG→BS (sofortige Übergabe ohne Marker-Poll) | bewusst nicht | Plan erlaubt Marker **oder** QProcess; Marker ist SSOT für Slice C |
| Cover-UUID „retired“ nach Tombstone | nicht-Ziel | Registry bleibt Nachweis; optional später |
| Mehrere Handoffs ohne Buch: UUID-Dialog nur in BS-GUI | ok / UX | Policy: kein Auto-Pick |
| Lebensende: GG-Papierkorb (`_trash`) vs. Windows-Papierkorb für GG-Pfad | offen | BS nutzt `send2trash` auch für GG-Ordner — Explorer-_trash_ sieht das nicht |
| Empty States in allen Shell-Dialogen flächig (Asset Manager, GG-Swap, …) | teilweise | Primär-CTA Leiste + Need-Book angeglichen; Rest laut next_Level Feinschliff |
| Handbuch-TOC / Stand Orchestrierung | erledigt (26.09.) | Kap. 16-Link + Kopf Stand/Version |
| Parallel A→J derselben UUID | abgefangen | Zweiter Pending-Handoff → Fehler |

Neue Funde hier eintragen, nicht nur im Chat.
