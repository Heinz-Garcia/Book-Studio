---
title: Impressum
print_title: false
description: Impressum
status: bookstudio
required: true
order: '6'
---

<!-- Eigene Absatzvorlage (Layout-Klasse "impressum"): linksbündig statt
Blocksatz; im Typst-Satz dasselbe über den Block drumherum. Leerzeilen um jeden ":::"-Block sind Pflicht, sonst liest Pandoc
die Zeile als Text. -->

```{=typst}
#block[#set par(justify: false)
```

::: {.impressum}
© 2026 Heinz-Garcia Verlag GmbH, Gaggenau\
Titel: {{BOOK_TITLE}}\
Reihe: Ich frage ja nur\
Autoren: KI Gemma4 und Wolfram Daniel Heinz-Garcia\
Reihenherausgeber: Heinz-Garcia

Umschlaggestaltung: Wolfram Daniel Heinz-Garcia

```{=typst}
#if bs-isbn != none [ISBN: #bs-isbn \ ]
```

::: {.callout-tip}
## Bonus-Material zum Buch

Zu diesem Band gibt es **ergänzende Materialien zum Download**
(passend zum Hinweis „Inkl. Bonus-Material“ auf dem Umschlag).

Scannen Sie den QR-Code mit der Kamera-App Ihres Smartphones
oder öffnen Sie den Link im Browser:

**[https://heinz-garcia.eu/](https://heinz-garcia.eu/)**

![QR-Code: Bonus-Material unter heinz-garcia.eu](/img/qr_bonus_heinz_garcia.png){fig-alt="QR-Code zur Website heinz-garcia.eu" width="3.2cm"}
:::

*Wichtiger medizinischer Hinweis und Haftungsausschluss*

Dieses Buch dient ausschließlich der Information und Weiterbildung. Die enthaltenen Inhalte, Ratschläge, Übungen und Empfehlungen stellen keinen medizinischen Rat dar und sind nicht als Ersatz für eine professionelle Beratung, Diagnose oder Behandlung durch approbierte Ärzte, Psychotherapeuten oder qualifiziertes Fachpersonal zu verstehen.

Der Autor und der Verlag übernehmen keine Haftung für Schäden, Verluste oder gesundheitliche Folgewirkungen, die direkt oder indirekt aus der Anwendung der in diesem Werk beschriebenen Informationen oder Methoden entstehen. Leserinnen und Leser sind aufgerufen, bei gesundheitlichen Beschwerden, chronischen Leiden oder vor Beginn einer neuen Behandlung stets eigenverantwortlich den Rat eines qualifizierten Mediziners einzuholen.

*Hinweis zu Telefonnummern, Adressen und sonstigen Angaben*

Alle Telefonnummern, Adressen, Öffnungszeiten, Fristen, Beträge und sonstigen Angaben in diesem Buch wurden mit Sorgfalt zusammengestellt, erfolgen jedoch ohne Gewähr. Sie können sich nach Redaktionsschluss ändern. Prüfen Sie wichtige Angaben vor Ort oder bei der zuständigen Stelle nach. Im akuten Notfall gilt in ganz Spanien die europäische Notrufnummer **112**.

*Transparenzhinweis zum Einsatz von Künstlicher Intelligenz (KI)*

Bei der Erstellung dieses Buches wurden Werkzeuge der Künstlichen Intelligenz (KI) eingesetzt.
:::

```{=typst}
]
```

```{=typst}
#pagebreak()
```
