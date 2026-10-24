#!/usr/bin/env bash
# Runs inside WSL: translate Windows paths (C:\... or C:/...) to /mnt/... and exec spim.
set -euo pipefail
args=()
for a in "$@"; do
    if [[ "$a" =~ ^[A-Za-z]:[\\/] ]]; then
        args+=("$(wslpath -u "$a")")
    else
        args+=("$a")
    fi
done
# Killing wsl.exe on the Windows side does not stop spim, so enforce the deadline here.
if [[ -n "${C2MIPS_SPIM_TIMEOUT:-}" ]]; then
    exec timeout -k 1 "$C2MIPS_SPIM_TIMEOUT" spim "${args[@]}"
fi
exec spim "${args[@]}"
