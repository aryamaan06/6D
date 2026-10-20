@echo off
setlocal
set "SIXD_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%SIXD_PYTHON%" (
  "%SIXD_PYTHON%" "%~dp0tools\open_preview.py"
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 "%~dp0tools\open_preview.py"
  ) else (
    python "%~dp0tools\open_preview.py"
  )
)
if errorlevel 1 pause
