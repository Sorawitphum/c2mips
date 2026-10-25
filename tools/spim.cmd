@echo off
rem Windows shim: run spim inside WSL (see README.md / tests/conftest.py).
rem Uses the default WSL distro; set C2MIPS_WSL_DISTRO to pick another one.
set "C2MIPS_CWD=%CD%"
set WSLENV=%WSLENV%:C2MIPS_SPIM_TIMEOUT:C2MIPS_CWD/p
if defined C2MIPS_WSL_DISTRO (
    wsl.exe -d %C2MIPS_WSL_DISTRO% --cd "%~dp0" -e bash ./spim-wsl.sh %*
) else (
    wsl.exe --cd "%~dp0" -e bash ./spim-wsl.sh %*
)
exit /b %ERRORLEVEL%
