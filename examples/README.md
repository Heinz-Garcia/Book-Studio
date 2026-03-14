# Unmanned Trigger – Beispiele

Diese Sammlung enthält sofort nutzbare Vorlagen für `--export-settings-json`.

## Dateien

- `unmanned_request.json` – Standard-Template
- `unmanned_request_ext_typstdoc.json` – Extension-Template (`EXT: typstdoc`)
- `unmanned_request_prepare_only.json` – Prepare-only in Kombination mit `--no-render`

## 1) Standard-Template

```bash
python unmanned_trigger.py \
  --book-path "Band_Stoffwechselgesundheit" \
  --structure-json "Band_Stoffwechselgesundheit/bookconfig/Pandemie_Diabetes_All_files_Gemini_sorted_v.3.json" \
  --md-source-path "Band_Stoffwechselgesundheit/content" \
  --export-settings-json "examples/unmanned_request.json"
```

## 2) Extension-Template (typstdoc)

```bash
python unmanned_trigger.py \
  --book-path "Band_Stoffwechselgesundheit" \
  --structure-json "Band_Stoffwechselgesundheit/bookconfig/Pandemie_Diabetes_All_files_Gemini_sorted_v.3.json" \
  --md-source-path "Band_Stoffwechselgesundheit/content" \
  --export-settings-json "examples/unmanned_request_ext_typstdoc.json"
```

## 3) Prepare-only (Dry Run)

```bash
python unmanned_trigger.py \
  --book-path "Band_Stoffwechselgesundheit" \
  --structure-json "Band_Stoffwechselgesundheit/bookconfig/Pandemie_Diabetes_All_files_Gemini_sorted_v.3.json" \
  --md-source-path "Band_Stoffwechselgesundheit/content" \
  --export-settings-json "examples/unmanned_request_prepare_only.json" \
  --no-render
```

## Optional: Orchestrierungs-Flags

Diese Flags lassen sich zu allen Aufrufen ergänzen:

- `--run-id "nightly-2026-03-14"`
- `--job-id "pipeline-4711"`
- `--log-file "logs/unmanned-run.log"`
- `--timeout-sec 1800`
- `--strict`
