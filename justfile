# The repo's own dots, so these work before the first apply has put it in ~/.local/bin.
dots := "home/.local/bin/dots"

[private]
default:
    @just --list

# Show what an apply would change
dry:
    {{dots}} --dry --diff

# Apply ~, and packages and /etc when their inputs changed
apply:
    {{dots}}

# Pull, then apply
update:
    {{dots}} update

# Every test and self-check, printing only failures
test:
    #!/usr/bin/env bash
    set -uo pipefail
    bad=0
    run() { out=$("$@" 2>&1 </dev/null) || { echo "FAIL ${*: -1}"; echo "$out"; bad=1; }; }
    for t in tools/*.test.py infra/home.py infra/releases.py infra/askonce.py infra/cmdline.py; do run python3 -I "$t"; done
    for t in tools/*.test.mjs; do run node "$t"; done
    ((bad)) || echo "all tests pass"
    exit $bad
