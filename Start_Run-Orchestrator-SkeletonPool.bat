@echo off
REM Skeleton-Pool pipeline — setzt .doc\skeleton.md um.
REM Prompt:  .doc\skeleton.md
REM Plan:    implementation_plan_skeleton.md
REM Pipeline: pipelines\skeleton_pool.toml
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Set-Location -LiteralPath '%~dp0'; python orchestrator.py --pipeline pipelines/skeleton_pool.toml %*"
