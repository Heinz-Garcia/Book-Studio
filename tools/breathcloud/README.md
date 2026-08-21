# Breathcloud (Hub packer SSOT)

Organic hub-centered word cloud packer used by **Cover-Schlagwortwolke → Freie Form**.

- Engine: `tools.breathcloud.engine` (`generate_breathcloud`)
- Gradient helpers: `tools.breathcloud.gradient`
- GUI: Stylecloud dialog (`ICON_HUB`); this package no longer ships a separate dialog
- CLI (still available):

```text
python -m tools.breathcloud `
  --hub NATURE `
  --text-file .\words.txt `
  --gradient "#1e5f8a,#2ec4b6,#c8f542" `
  -o breathcloud.png
```
