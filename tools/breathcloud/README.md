# Breathcloud

Autonomous organic word cloud (independent of Cover-Schlagwortwolke / stylecloud).

## What it does

1. **Hub word** — freely defined; the cloud gathers around it.
2. **Free-breathing form** — dense spiral packing from the center; crop to ink (no rectangle hull).
3. **Gradient** — horizontal linear gradient via comma-separated hex colors.

## CLI

```powershell
python -m tools.breathcloud `
  --hub NATURE `
  --text-file .\words.txt `
  --gradient "#1e5f8a,#2ec4b6,#c8f542" `
  -o breathcloud.png
```

## GUI

Book Studio → Plugins → **Breathcloud — organische Wortwolke…**

- **Textquelle** wie Cover-Schlagwortwolke: aktuelles Buch / Datei / Freitext
  (Defaults aus Preset ``freeForm``).
- **Farbverlauf** über drei Farbfelder (System-Farbdialog), kein Hex-Tippen.
- **Kernwort** frei; Begleitwörter aus der gewählten Quelle.
