"""
Binaries installed from pinned upstream releases, listed in releases.toml.
apply.py runs `install` when that file or this one changes.

    python3 -I infra/releases.py           # self-check
    python3 -I infra/releases.py install   # install every entry
"""
import hashlib
import os
import pathlib
import shutil
import sys
import tarfile
import tempfile
import tomllib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]


def entries():
    return tomllib.loads((ROOT / "infra/releases.toml").read_text())


def install(entry, home):
    """Puts entry's member at its target under home. The sha256 is checked
    before the archive is opened, and the member replaces the target in one
    rename, so a running copy keeps its old inode."""
    target = pathlib.Path(home) / entry["target"]
    url = entry["url"].format(version=entry["version"])
    with tempfile.TemporaryDirectory() as tmp:
        archive = pathlib.Path(tmp, "release")
        with urllib.request.urlopen(url, timeout=60) as response, archive.open("wb") as out:
            shutil.copyfileobj(response, out)
        got = hashlib.sha256(archive.read_bytes()).hexdigest()
        if got != entry["sha256"]:
            raise ValueError(f"{url}: sha256 {got}, pinned {entry['sha256']}")
        # In the target's directory: /tmp is another filesystem, and a rename across them fails.
        fd, part = tempfile.mkstemp(dir=target.parent)
        try:
            with tarfile.open(archive) as tar, os.fdopen(fd, "wb") as out:
                shutil.copyfileobj(tar.extractfile(entry["member"]), out)
            os.chmod(part, 0o755)
            os.replace(part, target)
        except BaseException:
            os.unlink(part)
            raise


if __name__ == "__main__" and sys.argv[1:] == ["install"]:
    for entry in entries().values():
        install(entry, pathlib.Path.home())
elif __name__ == "__main__" and sys.argv[1:]:
    # Otherwise a typo in apply.py's call would run the self-check, exit 0 and let the gate stamp.
    sys.exit("usage: releases.py [install]")
elif __name__ == "__main__":
    import io
    import stat

    for name, entry in entries().items():
        assert len(entry["sha256"]) == 64 and "{version}" in entry["url"], name
        assert not entry["target"].startswith(("/", "~")), name

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        # Where an install that ignores its home argument would write.
        os.environ["HOME"] = str(tmp / "real-home")
        archive = tmp / "release-1.0.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for name, body in (("decoy", b"decoy"), ("dir/tool", b"new binary")):
                info = tarfile.TarInfo(name)
                info.size = len(body)
                tar.addfile(info, io.BytesIO(body))
        home = tmp / "home"
        target = home / ".local/bin/tool"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"old binary")
        old = target.stat().st_ino
        entry = {"version": "1.0", "url": f"file://{tmp}/release-{{version}}.tar.gz", "member": "dir/tool",
                 "target": ".local/bin/tool", "sha256": "0" * 64}

        try:
            install(entry, home)
        except ValueError:
            pass
        else:
            raise AssertionError("a wrong sha256 installed")
        assert target.read_bytes() == b"old binary" and target.stat().st_ino == old, "a wrong sha256 touched the target"
        assert os.listdir(target.parent) == ["tool"], os.listdir(target.parent)

        # Fails after mkstemp, so only the cleanup keeps the partial file out of the target's directory.
        entry["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        entry["member"] = "missing"
        try:
            install(entry, home)
        except KeyError:
            pass
        else:
            raise AssertionError("a missing member installed")
        assert target.read_bytes() == b"old binary" and target.stat().st_ino == old, "a failed extract touched the target"
        assert os.listdir(target.parent) == ["tool"], os.listdir(target.parent)

        entry["member"] = "dir/tool"
        with target.open("rb") as running:
            install(entry, home)
            assert running.read() == b"old binary", "the install wrote into the old file"
        assert target.read_bytes() == b"new binary", target.read_bytes()
        assert stat.S_IMODE(target.stat().st_mode) == 0o755, oct(target.stat().st_mode)
        assert target.stat().st_ino != old, "the install wrote in place"
        assert os.listdir(target.parent) == ["tool"], os.listdir(target.parent)
        assert not (tmp / "real-home").exists(), "the install ignored its home"
    print("releases OK")
