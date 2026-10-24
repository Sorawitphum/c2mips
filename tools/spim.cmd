@echo off
rem Windows shim: run spim from the default WSL distro (see tests/conftest.py).
set WSLENV=%WSLENV%:C2MIPS_SPIM_TIMEOUT
wsl.exe --cd "%~dp0" -e bash ./spim-wsl.sh %*
