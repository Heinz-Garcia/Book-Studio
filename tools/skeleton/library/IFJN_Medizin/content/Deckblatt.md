---
title: "Deckblatt"
print_title: false
description: "Deckblatt"
status: bookstudio
required: true
order: "1"
comment: "Platzhalter für das Deckblatt: ein separates, seitenfüllendes Cover-Bild ohne Ränder. YAML-title erscheint nicht im PDF (required → still)."
---

Platzhalter für das Cover. Sobald ein Cover-Bild bereitsteht: Bild-Datei nach
`img/` im Buch-Root legen (root-relativer Pfad mit führendem `/`) und diesen
Absatz durch einen Typst-Rohblock (```` ```{=typst} ````) mit folgendem Inhalt
ersetzen:

    #page(margin: 0pt)[
      #image("/img/<Dateiname>.png", width: 100%, height: 100%, fit: "cover")
    ]

Die YAML-``title`` wird beim Typst-Render standardmäßig unterdrückt
(``required: true`` / ``print_title: false``). Sichtbare Kapitelüberschriften
nur für Inhaltkapitel oder mit ``print_title: true``.

```{=typst}
#pagebreak()
```
