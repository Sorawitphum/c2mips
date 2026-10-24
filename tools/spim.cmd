@echo off
rem Windows shim: run spim from the default WSL distro (see tests/conftest.py).
set "C2MIPS_CWD=%CD%"
set WSLENV=%WSLENV%:C2MIPS_SPIM_TIMEOUT:C2MIPS_CWD/p
wsl.exe --cd "%~dp0" -e bash ./spim-wsl.sh %*
