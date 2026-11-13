#!/usr/bin/env python3
"""python3 -I tools/gpg-import.test.py — checks infra/scripts/import-gpg-key.sh."""
import os
import pathlib
import subprocess
import tempfile

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "infra/scripts/import-gpg-key.sh"
MARKER = b"-----BEGIN PGP PRIVATE KEY BLOCK-----\nmarker\n"

# age is the real one. Each stub reads its
# behaviour from the temp HOME, so a case only writes files.
STUBS = {
    "git": 'echo ABCD1234\n',
    "gpg": '''case "$1" in
  --list-secret-keys) test -e "$HOME/has-key" ;;
  --import) cat > "$HOME/imported" ;;
esac
''',
    "rbw": '''echo "$*" >> "$HOME/rbw-calls"
test "$*" = "get age-key" || exit 1
test -e "$HOME/rbw-fails" && exit 1
test -e "$HOME/rbw-empty" && exit 0
cat "$HOME/age-key"
''',
}


def setup(tmp):
    home = pathlib.Path(tmp)
    bin_ = home / "bin"
    bin_.mkdir()
    for name, body in STUBS.items():
        (bin_ / name).write_text("#!/bin/bash\n" + body)
        (bin_ / name).chmod(0o755)
    subprocess.run(["age-keygen", "-o", str(home / "age-key")], check=True, capture_output=True)
    recipient = subprocess.run(["age-keygen", "-y", str(home / "age-key")], check=True, capture_output=True, text=True).stdout.strip()
    enc = home / ".local/share/gpg-key.asc.age"
    enc.parent.mkdir(parents=True)
    subprocess.run(["age", "-r", recipient, "-o", str(enc)], input=MARKER, check=True)
    return home


def run(home):
    env = {**os.environ, "HOME": str(home), "PATH": f"{home / 'bin'}:{os.environ['PATH']}"}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True).returncode


with tempfile.TemporaryDirectory() as tmp:
    home = setup(tmp)
    code = run(home)
    assert code == 0, f"key missing, rbw has it: exit {code}"
    imported = home / "imported"
    assert imported.exists() and imported.read_bytes() == MARKER, f"gpg got {imported.read_bytes() if imported.exists() else 'nothing'!r}"

with tempfile.TemporaryDirectory() as tmp:
    home = setup(tmp)
    (home / "rbw-fails").touch()
    code = run(home)
    assert code != 0, "rbw failed but the script exited 0"
    imported = home / "imported"
    assert not imported.exists() or imported.read_bytes() == b"", f"gpg imported {imported.read_bytes()!r} after rbw failed"

with tempfile.TemporaryDirectory() as tmp:
    home = setup(tmp)
    (home / "has-key").touch()
    code = run(home)
    assert code == 0, f"key already imported: exit {code}"
    assert not (home / "rbw-calls").exists(), "rbw called though the key is already imported"

with tempfile.TemporaryDirectory() as tmp:
    home = setup(tmp)
    (home / "rbw-empty").touch()
    code = run(home)
    assert code != 0, "rbw returned an empty note but the script exited 0"
    imported = home / "imported"
    assert not imported.exists() or imported.read_bytes() == b"", f"gpg imported {imported.read_bytes()!r} from an empty note"

print("gpg-import OK")
