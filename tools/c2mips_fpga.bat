@echo off
rem FPGA Studio custom compiler (ADR-009):  c2mips_fpga.bat <file.c>
rem Writes <file.c>.s next to the source and prints the same assembly on stdout.
rem Errors go to stderr with a non-zero exit code. Finds the repo from this file's location.
setlocal
if "%~1"=="" (
    echo usage: %~nx0 file.c 1>&2
    exit /b 2
)
set "REPO=%~dp0.."
set "PY=%REPO%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "PYTHONPATH=%REPO%;%PYTHONPATH%"
"%PY%" -m c2mips --target fpga "%~1" -o "%~1.s"
if errorlevel 1 exit /b %ERRORLEVEL%
type "%~1.s"
exit /b 0
