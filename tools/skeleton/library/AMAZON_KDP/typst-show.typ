// Blendet Kapitel-Ueberschriften vor/inkl. dem Deckblatt aus (index.md +
// Deckblatt.md selbst), damit das Cover wirklich die allererste sichtbare
// Seite ist -- Deckblatt.md setzt "past-cover" per #past-cover.update(true)
// direkt nach seinem Vollbild-Bild.
#let past-cover = state("past-cover", false)
#show heading.where(level: 1): it => context {
  if past-cover.get() { it } else { [] }
}

#show: doc => article(
$if(section-numbering)$
  sectionnumbering: "$section-numbering$",
$endif$
$if(toc)$
  toc: $toc$,
$endif$
$if(toc-title)$
  toc_title: [$toc-title$],
$endif$
$if(toc-indent)$
  toc_indent: $toc-indent$,
$endif$
  toc_depth: $toc-depth$,
  doc,
)
