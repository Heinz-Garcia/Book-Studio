// Quarto Book setzt aus jeder Chapter-YAML-``title`` ein Level-1-Heading.
// Standard: diese Headings sind UNSICHTBAR (Vakat, Schmutztitel, Deckblatt, …)
// und nicht im manuellen ``#outline()`` (outlined: false).
// Sichtbare Kapitelüberschriften erzeugt der PreProcessor nur bei Opt-in
// (print_title) als ``#heading(…, outlined: true)`` im sichtbaren Fenster.
//
// toc: false — Quarto's Auto-TOC wuerde VOR Deckblatt/Titel gezeichnet
// (unabhaengig von der chapters-Reihenfolge). Das manuelle IVZ liegt in
// content/IVZ.md (#outline()). YAML format.typst.toc wird hier bewusst
// ignoriert, damit ein toc: true die Wunschstruktur nicht wieder zerstoert.
#let chapter-titles-visible = state("chapter-titles-visible", false)
// Alias: aeltere Deckblatt.md riefen ``#past-cover.update(true)`` auf.
// Kein Effekt mehr auf Titel-Sichtbarkeit (Compat, damit Raw-Typst nicht knallt).
#let past-cover = state("past-cover", false)

// Vakatseiten (automatisch eingefuegte Leerseiten durch
// #pagebreak(to: "odd"/"even"), z. B. damit ein Kapitel auf einer rechten
// Seite beginnt): klassische Buchsatz-Konvention ist "mitgezaehlt, aber
// nicht gedruckt" — die Folgeseite behaelt ihre korrekte Nummer, nur auf
// der eingefuegten Leerseite selbst erscheint keine Ziffer. Ein
// state()-Ansatz (vor/nach dem pagebreak umschalten) hat sich als
// zeitlich instabil erwiesen (faerbt auf die VORHERIGE echte Seite ab,
// empirisch getestet) — der show-Selektor direkt auf den pagebreak-Typ
// wirkt dagegen exakt nur auf die dadurch neu erzeugte(n) Seite(n).
#show selector.or(
  pagebreak.where(to: "odd"),
  pagebreak.where(to: "even"),
): set page(header: none, footer: none)

// Kapitelzaehlung (9, 11, 13, 15 … statt 1, 2, 3, 4):
// counter(heading) steppt fuer JEDE Level-1-Heading, sobald ihre eigene
// ``numbering`` bei der KONSTRUKTION nicht ``none`` ist — unabhaengig davon,
// was ein show-Regel *danach* aus ihr macht. Weder ``none`` zurueckgeben
// noch mit #metadata() ersetzen verhindert das Stepping (beides empirisch
// geprueft, siehe .doc/ Notizen). Der einzig wirksame Hebel: die Nummerierung
// schon beim Konstruieren abschalten — per Selektor, nicht per Inhalt.
#show heading.where(level: 1): set heading(numbering: none)

// ``bs-section-numbering``: buchweit einmal gesetzte Kopie von
// ``$section-numbering$`` (Pandoc-Template-Variable, nur HIER in
// typst-show.typ ausgewertet). chapter_title_render.py injiziert pro
// sichtbarer Kapitelheading ein EIGENES, aus dem Titel abgeleitetes Label
// (nicht ein geteiltes <bs-visible-chapter> — Typst registriert jedes
// Label automatisch als PDF-Sprungziel, ein geteiltes Label wuerde also
// alle Kapitel-IVZ-Eintraege buchweit auf ein einziges Kapitel kollidieren
// lassen) und darin direkt einen ``show ....and(<label>): set
// heading(numbering: bs-section-numbering)``-Aufruf mit, der diese
// Variable braucht, weil Inhaltsdateien selbst kein ``$section-numbering$``
// mehr ausgewertet bekommen (nur die Template-Datei wird durch Pandoc
// substituiert).
$if(section-numbering)$
#let bs-section-numbering = "$section-numbering$"
$else$
#let bs-section-numbering = none
$endif$

#show heading.where(level: 1): set heading(outlined: false, bookmarked: false)

#show heading.where(level: 1): it => context {
  if chapter-titles-visible.get() {
    it
  } else {
    // Nur noch Sichtbarkeit/Outline betroffen — die Nummerierung ist fuer
    // diese Headings bereits oben (vor Konstruktion) deaktiviert und zaehlt
    // daher nicht mehr mit.
    [#metadata(("bs-silent-chapter", it.body))]
  }
}

// IVZ-Gliederung: Kapitel-Ebene (Level 1) optisch von den Fragen (Level 2)
// abgesetzt -- sonst laufen beide Ebenen im selben Schriftschnitt/-gewicht
// zu einer ununterscheidbaren Textwueste zusammen. Fett + Abstand davor
// gruppiert die Fragen sichtbar unter ihr Kapitel; Level 2 bleibt Standard.
#show outline.entry.where(level: 1): it => {
  v(0.75em, weak: true)
  strong(it)
}

// Schusterjunge/Hurenkind: Überschrift nicht allein am Seitenende;
// Absatz-Witwen/Waisen explizit absichern (Typst-Default ist 100%).
#show heading: set block(sticky: true)
#set text(costs: (widow: 100%, orphan: 100%))

#show: doc => article(
$if(section-numbering)$
  sectionnumbering: "$section-numbering$",
$endif$
  toc: false,
$if(toc-title)$
  toc_title: [$toc-title$],
$endif$
$if(toc-indent)$
  toc_indent: $toc-indent$,
$endif$
  toc_depth: $toc-depth$,
  doc,
)
