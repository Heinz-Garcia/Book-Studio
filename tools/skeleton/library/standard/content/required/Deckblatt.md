---
title: "Deckblatt"
description: "Deckblatt"
status: bookstudio
order: "5"
comment: "Platzhalter für das Deckblatt: ein separates, seitenfüllendes Cover-Bild ohne Ränder. Titel.md bleibt der reine Schmutztitel (nur Text, kein Bild)."
---

Platzhalter für das Cover. Sobald ein Cover-Bild bereitsteht: Bild-Datei nach
`img/` im Buch-Root legen (root-relativer Pfad mit führendem `/`) und diesen
Absatz durch einen Typst-Rohblock (```` ```{=typst} ````) mit folgendem Inhalt
ersetzen:

    #page(margin: 0pt)[
      #image("/img/<Dateiname>.png", width: 100%, height: 100%, fit: "cover")
    ]
    #past-cover.update(true)

Das `#past-cover.update(true)` ist Pflicht (siehe `typst-show.typ`): erst
danach werden Kapitel-Überschriften wieder normal angezeigt, sonst bleiben
auch spätere Kapitel unsichtbar.

```{=typst}
#pagebreak()
```
