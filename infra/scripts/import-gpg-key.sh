#!/bin/bash
# Imports the git signing key unless the keyring has it. Piped from age to gpg
# because age -o writes its output 0644, which leaves the private key
# world-readable.
# tools/gpg-import.test.py checks it.
set -euo pipefail
# Assigned first so set -e stops on a missing key: an empty one would match
# any secret key and skip the import.
key="$(git config --global --get user.signingkey)"
gpg --list-secret-keys "$key" >/dev/null 2>&1 && exit 0
rbw get age-key | age -d -i - "$HOME/.local/share/gpg-key.asc.age" | gpg --import
