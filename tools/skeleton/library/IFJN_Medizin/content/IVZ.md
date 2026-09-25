---
title: Inhaltsverzeichnis
print_title: false
description: Inhaltsverzeichnis
status: bookstudio
required: true
order: '8'
comment: >-
  Manuelle Platzierung des Inhaltsverzeichnisses. Setzt voraus, dass format.typst.toc
  in der _quarto.yml auf false steht (Tools -> Quarto.yml konfigurieren...) -- sonst
  rendert Quarto zusaetzlich sein eigenes IVZ automatisch VOR Deckblatt/Titel, unabhaengig
  von der Position im Buchbaum. Outline-Einrueckung feste 1em statt auto. Ueberschrift
  manuell per chapter-titles-visible-Toggle sichtbar gemacht (siehe typst-show.typ) --
  ein einfaches Markdown-``# Inhalt`` wird von der globalen Level-1-Unterdrueckung
  ebenso verschluckt wie die (hier bewusst unterdrueckte) YAML-title-Heading.
---

```{=typst}
#chapter-titles-visible.update(true)
#heading(level: 1, outlined: false, bookmarked: false)[Inhaltsverzeichnis]
#chapter-titles-visible.update(false)
#outline(indent: 1em)
#pagebreak()
```
