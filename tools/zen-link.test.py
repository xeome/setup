#!/usr/bin/env python3
"""python3 -I tools/zen-link.test.py — checks home/.chezmoiscripts/run_after_link-zen-chrome.sh."""
import os
import pathlib
import subprocess
import tempfile

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "home/.chezmoiscripts/run_after_link-zen-chrome.sh"
PREFS = (
    'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);',
    'user_pref("xpinstall.signatures.required", false);',
    'user_pref("zen.urlbar.replace-newtab", false);',
    'user_pref("zen.view.window.scheme", 2);',
)
HAND = "/* written by hand */\n"


def run(home):
    subprocess.run(["bash", str(SCRIPT)], env={**os.environ, "HOME": str(home)}, check=True)


def snapshot(zen):
    snap = {}
    for p in sorted(zen.rglob("*")):
        if p.is_symlink():
            snap[p] = ("link", os.readlink(p))
        elif p.is_file():
            snap[p] = ("file", p.read_bytes(), p.stat().st_mtime_ns)
    return snap


with tempfile.TemporaryDirectory() as tmp:
    home = pathlib.Path(tmp)
    zen = home / ".zen"
    linked = zen / "ab12.Default (release)"
    hand = zen / "cd34.Default (alpha)"
    for p in (linked, hand):
        p.mkdir(parents=True)
    (hand / "chrome").mkdir()
    (hand / "chrome/userChrome.css").write_text(HAND)
    # A hand-written user.js with no final newline, which the script must not glue onto.
    (hand / "user.js").write_text('user_pref("browser.startup.page", 3);')
    (zen / "profiles.ini").write_text(f"[Profile0]\nPath={linked.name}\n\n[Profile1]\nPath={hand.name}\n")

    run(home)
    first = snapshot(zen)
    run(home)
    second = snapshot(zen)

    hometab = str(home / ".config/zen/hometab")
    for p in (linked, hand):
        proxy = p / "extensions/hometab@xeome"
        assert proxy.is_file() and proxy.read_text().strip() == hometab, f"{p.name}: proxy {proxy.read_text() if proxy.exists() else 'missing'!r}"
        lines = (p / "user.js").read_text().splitlines()
        for pref in PREFS:
            assert lines.count(pref) == 1, f"{p.name}: {pref} appears {lines.count(pref)} times"
    assert (hand / "user.js").read_text().startswith('user_pref("browser.startup.page", 3);\n')
    assert os.readlink(linked / "chrome/userChrome.css") == str(home / ".config/zen/userChrome.css")
    hand_css = hand / "chrome/userChrome.css"
    assert not hand_css.is_symlink() and hand_css.read_text() == HAND, "hand-written userChrome.css was replaced"

    changed = [str(p.relative_to(zen)) for p in first.keys() | second.keys() if first.get(p) != second.get(p)]
    assert not changed, f"the second run changed {changed}"

    voicenote = str(home / ".config/zen/voicenote")
    answer = home / ".local/state/dots/voicenote"
    proxies = [p / "extensions/voicenote@xeome" for p in (linked, hand)]
    assert not any(v.exists() for v in proxies), "voicenote linked with no answer file"

    answer.parent.mkdir(parents=True)
    answer.write_text("yes")
    run(home)
    first = snapshot(zen)
    run(home)
    assert snapshot(zen) == first, "a second run after yes changed files"
    for v in proxies:
        assert v.is_file() and v.read_text().strip() == voicenote, f"{v}: {v.read_text() if v.exists() else 'missing'!r}"

    answer.unlink()
    run(home)
    assert all(v.is_file() for v in proxies), "voicenote unlinked when the answer file was deleted"

    answer.write_text("no")
    run(home)
    assert not any(v.exists() for v in proxies), "voicenote still linked after a later no"
    for p in (linked, hand):
        assert (p / "extensions/hometab@xeome").read_text().strip() == hometab, f"{p.name}: no stopped hometab"

print("zen-link OK")
