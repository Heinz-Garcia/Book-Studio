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

#show heading.where(level: 1): set heading(outlined: false, bookmarked: false)

#show heading.where(level: 1): it => context {
  if chapter-titles-visible.get() {
    it
  } else {
    // Wichtig: ``none`` allein kann den Heading-Zähler trotzdem erhöhen
    // (Quarto-YAML-Titel + print_title-Injection → 9, 11, 13, 15 …).
    // Metadata statt Heading: weder sichtbar noch Zähler noch Outline.
    [#metadata(("bs-silent-chapter", it.body))]
  }
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
