@echo off
setlocal
rem Use only an explicit override, this project's environment, or installed Python.
if defined SIXD_PYTHON goto explicit_python
if exist "%~dp0..\.venv\Scripts\python.exe" goto project_python
where py >nul 2>nul
if errorlevel 1 goto installed_programs
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto installed_programs
py -3 %*
exit /b %errorlevel%

:installed_programs
rem An installed Python can work even if its launcher registration/PATH is missing.
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
  if exist "%%~fD\python.exe" (
    "%%~fD\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 (
      set "SIXD_SELECTED=%%~fD\python.exe"
      goto run_installed
    )
  )
)
where python >nul 2>nul
if errorlevel 1 goto python_missing
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto python_missing
python %*
exit /b %errorlevel%

:run_installed
"%SIXD_SELECTED%" %*
exit /b %errorlevel%

:explicit_python
if not exist "%SIXD_PYTHON%" (
  echo 6D: SIXD_PYTHON does not point to an existing Python executable.
  exit /b 1
)
"%SIXD_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
  echo 6D: SIXD_PYTHON must be a working Python 3.10 or newer executable.
  exit /b 1
)
"%SIXD_PYTHON%" %*
exit /b %errorlevel%

:project_python
"%~dp0..\.venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
  echo 6D: The project environment cannot run. Rename .venv and run Setup-6D.cmd again.
  exit /b 1
)
"%~dp0..\.venv\Scripts\python.exe" %*
exit /b %errorlevel%

:python_missing
echo 6D needs an installed Python 3.10 or newer. No application data was changed.
echo Download Python from https://www.python.org/downloads/windows/ and enable Add Python to PATH.
echo Then run Setup-6D.cmd. You can also set SIXD_PYTHON to your installed python.exe.
exit /b 1
