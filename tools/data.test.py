#!/usr/bin/env python3
"""python3 -I tools/data.test.py — fails when a value of infra/data.py is written
out anywhere else in the repo: a colour of the palette, the terminals or the
console, in any notation a config spells one in, or a machine's hostname.

Every text file git tracks or would track is read. Pure black and white are
skipped. The translucent colours are white or black with an alpha. An rgba()
is a copy of one when its alpha is the token's to three places: to the two
that rgba() renders, a plain half-white would be one too.
"""
import pathlib
import re
import runpy
import subprocess
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
data = types.SimpleNamespace(**runpy.run_path(str(ROOT / "infra/data.py")))

PLAIN = {"000000", "ffffff"}


def colours(node, name):
    if isinstance(node, str):
        yield name, node[1:].lower()
    else:
        for k, v in node.items() if isinstance(node, dict) else enumerate(node):
            yield from colours(v, f"{name}.{k}")


OPAQUE, SHEER = {}, {}
for name, h in [*colours(data.PALETTE, "PALETTE"), *colours(data.TERMINAL, "TERMINAL"),
                *colours(data.CONSOLE, "CONSOLE")]:
    assert h[:6] in PLAIN or len(h) == 6, f"{name}: a translucent colour that is not black or white"
    if len(h) == 8:
        SHEER.setdefault((data.rgb("#" + h), int(h[6:], 16) / 255), name)
    elif h not in PLAIN:
        OPAQUE.setdefault(h, name)

HEX = re.compile(r"(?<![0-9a-f])(?:[0-9a-f]{8}|[0-9a-f]{6})(?![0-9a-f])", re.I)
BYTES = re.compile(r"0x([0-9a-f]{2})\s*,\s*0x([0-9a-f]{2})\s*,\s*0x([0-9a-f]{2})", re.I)
# Overlapping, so a colour is found wherever it starts in a longer list.
TRIPLE = re.compile(r"(?<![\d.])(?=(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?!\d))")
RGBA = re.compile(r"rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d*\.?\d+)\s*\)")
LIST = re.compile(r"(?<![\d,])\d{1,3}(?:,\d{1,3}){7,}(?![\d,])")
HOST = re.compile("|".join(map(re.escape, data.MACHINES)))


def found(text):
    for m in HEX.finditer(text):
        run = m[0].lower()
        # Eight digits are an opaque colour with an alpha before or after it.
        name = OPAQUE.get(run) if len(run) == 6 else OPAQUE.get(run[2:]) or OPAQUE.get(run[:6])
        if name:
            yield m.start(), f"{m[0]} is {name}"
    for m in BYTES.finditer(text):
        if name := OPAQUE.get("".join(m.groups()).lower()):
            yield m.start(), f"{m[0]} is {name}"
    for m in TRIPLE.finditer(text):
        if all(int(c) < 256 for c in m.groups()) and (name := OPAQUE.get("%02x%02x%02x" % tuple(map(int, m.groups())))):
            yield m.start(), f"{', '.join(m.groups())} is {name}"
    for m in RGBA.finditer(text):
        for (rgb, alpha), name in SHEER.items():
            if ", ".join(m.groups()[:3]) == rgb and abs(float(m[4]) - alpha) < 0.001:
                yield m.start(), f"{m[0]} is {name}"
    # One list per channel, as the kernel's vt.default_red/grn/blu take them.
    lists = [(m.start(), [int(c) for c in m[0].split(",")]) for m in LIST.finditer(text)]
    for (at, r), (_, g), (_, b) in zip(lists, lists[1:], lists[2:]):
        if len(r) == len(g) == len(b):
            names = {OPAQUE.get("%02x%02x%02x" % c) for c in zip(r, g, b) if max(c) < 256} - {None}
            if names:
                yield at, f"three channel lists hold {', '.join(sorted(names))}"
    for m in HOST.finditer(text):
        yield m.start(), f"{m[0]} is a key of MACHINES"


tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard"],
                         capture_output=True, text=True, check=True).stdout.splitlines()
copies = []
for rel in tracked:
    path = ROOT / rel
    if rel == "infra/data.py" or not path.is_file():
        continue
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        continue
    copies += [f"{rel}:{text.count(chr(10), 0, at) + 1}: {what}" for at, what in sorted(found(text))]

assert not copies, "values of infra/data.py written out by hand:\n" + "\n".join(copies)
print("data OK")
