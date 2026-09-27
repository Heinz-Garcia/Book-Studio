# Vollautomatik

Stand: 2026-09-27 · Plan und Fortschritt: [automatik_gg_bis_docx.md](automatik_gg_bis_docx.md)

Die Nacharbeit am Ende des Laufs ist fertig: Nach einem Lauf aus der El-Pitugrafo-Oberfläche öffnet sich jetzt automatisch ein Dialog in Book Studio, in dem du die offenen Punkte beantwortest. Beide Repos sind committet (GG v31.73.0, Book Studio v2.90), die Test-Gates und der Test über beide Apps sind grün.

**Vollständiger Pfad zur DOCX:**
`C:\Users\RDP-Nutzer\IDE\Book_Studio_Unleashed\production\books\Hansel_und_Gretel\export\doclayout\Prosa_Layout.docx`

Der Dialog zeigt denselben Pfad ganz oben, mit „Öffnen“ und „Ordner“.

**1. Gegenüberstellung Vorfassung ↔ übernommene Fassung**
- Eine HTML-Seite zeigt je übernommenem Kapitel beide Fassungen Absatz für Absatz nebeneinander. Gestrichene und neue Wörter sind markiert, unveränderte Absätze grau.
- Dazu stehen Wortzahl und Befundpunkte vorher/nachher, das Urteil des Vergleichs mit Modell und Zeit, die Begründung, die genannten Nachteile und die Befunde der Vorfassung.
- **Neu gefunden und behoben:** Der Vergleich mischt die Reihenfolge der beiden Fassungen, und die Begründung spricht nur von „Fassung A“ und „Fassung B“. Ohne Zuordnung ist sie nicht lesbar. Die Seite sagt jetzt, welche Fassung A war. Das steht nur dort, wenn die gespeicherten Prüfsummen zu beiden Texten passen.
- Für deinen HuG-Lauf habe ich sie nachträglich erzeugt: `production\runs\f3bf0290-…\automatik_gegenueberstellung.html`. Bei allen 6 Kapiteln war die übernommene Fassung „A“. Insgesamt sank die Wortzahl von 2.278 auf 1.296. Die Begründungen nennen als Grund gestrichene Zutaten, die nicht im Schreibauftrag standen.

**2. Fehlende Ressourcen**
- Je Datei gibt es „Datei wählen…“ oder „Platzhalter einsetzen“. Der Platzhalter ist ein beschriftetes Bild am erwarteten Ort.
- Bei HuG betrifft das `/img/qr_bonus_heinz_garcia.png` im Impressum.

**3. Absatzformate ohne Zuordnung**
- Du wählst ein Format der Vorlage oder „Als Fließtext fortsetzen“. Die Auswahl ist nicht vorbelegt, damit ein versehentlicher Klick nichts falsch zuordnet.
- Die Zuordnung wird in die Formatvorlage geschrieben, gilt also auch für andere Bücher mit derselben Vorlage.
- Dazu gibt es einen Shortcut in den Layout-Editor.
- Bei HuG betrifft das `.produktion`, die Klasse, mit der GG den ganzen Kapiteltext umschließt.

**4. Pflichtseiten mit Link auf die Vorlage**
- Je Seite gibt es „Im Buch öffnen“ und „Vorlage öffnen“. Mit ★ markiert ist die Vorlage, die wörtlich gleich ist, bei gleichwertigen die des Laufprofils (hier Prosa_Standard). Die übrigen Profile stehen im Menü daneben.
- Dazu gibt es einen Shortcut in den Skeleton-Editor.
- Nach deinen Änderungen setzt „DOCX neu setzen“ die DOCX erneut.

Der Dialog ist nicht modal. Aus einem modalen Dialog heraus bekämen Layout- und Skeleton-Editor keine Eingaben, das hat ein Wächtertest abgefangen.

Für den HuG-Lauf von vorhin kannst du den Dialog jetzt öffnen. Im Book-Studio-Ordner:
```
.venv\Scripts\python -m tools.automatik nacharbeit --profil production\runs\f3bf0290-9c64-4c7c-a4ae-13b3273c8633\automatik.json
```
