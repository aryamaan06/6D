@echo off
setlocal
call "%~dp0tools\run_python.cmd" "%~dp0tools\setup_local.py" %*
set "SIXD_EXIT=%errorlevel%"
if not "%SIXD_EXIT%"=="0" if "%~1"=="" pause
exit /b %SIXD_EXIT%
