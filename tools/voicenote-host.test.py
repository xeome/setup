#!/usr/bin/env python3
"""python3 -I tools/voicenote-host.test.py — checks home/dot_local/bin/executable_voicenote-host
against a stub whisper-cli on PATH, speaking Firefox's native messaging framing."""
import base64
import hashlib
import json
import os
import pathlib
import re
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOST = ROOT / "home/dot_local/bin/executable_voicenote-host"
# deploy.py downloads the models to these paths, and the host must load them from there.
MODEL = re.search(r'^WHISPER_MODEL = "([^"]+)"', (ROOT / "infra/deploy.py").read_text(), re.M)[1]
host_model = re.search(r'^MODEL = "([^"]+)"', HOST.read_text(), re.M)[1]
assert host_model == MODEL, f"the host loads {host_model}, deploy.py downloads {MODEL}"
VAD = re.search(r'^VAD_MODEL = "([^"]+)"', (ROOT / "infra/deploy.py").read_text(), re.M)[1]
host_vad = re.search(r'^VAD = "([^"]+)"', HOST.read_text(), re.M)[1]
assert host_vad == VAD, f"the host loads VAD model {host_vad}, deploy.py downloads {VAD}"
# Like whisper-cli 1.9.5 with -f -: stdout carries only the -o* formats asked for, so without
# -otxt it prints nothing and exits 0. -otxt -nt writes one line per segment, no leading space.
STUB = """#!/usr/bin/env python3
import json, os, sys
d = os.environ["STUB_DIR"]
open(os.path.join(d, "argv.json"), "w").write(json.dumps(sys.argv[1:]))
open(os.path.join(d, "stdin"), "wb").write(sys.stdin.buffer.read())
if os.environ.get("STUB_FAIL") == "quiet":
    sys.exit(3)
if os.environ.get("STUB_FAIL") == "silent":
    sys.stderr.write("'--output-file -' used without any other '--output-*'\\n")
    sys.exit(0)
if os.environ.get("STUB_FAIL"):
    sys.stderr.write("whisper_init: loading model\\nerror: failed to read audio data\\n")
    sys.exit(2)
if "-otxt" in sys.argv:
    sys.stdout.write("Merhaba, nasılsın?\\nYarın görüşürüz.\\n")
"""
# syslog is a lib-dynload module, so this on PYTHONPATH shadows it: nothing reaches the real
# journal.
SYSLOG = """import json, os
_ident = None
def openlog(ident=None, *args):
    global _ident
    _ident = ident
def syslog(*args):
    with open(os.environ["SYSLOG_LOG"], "a") as f:
        f.write(json.dumps([_ident, args[-1]]) + "\\n")
"""
# 10244 bytes: a 0.3 s note after its 44-byte header.
WAV = b"RIFF" + bytes(range(256)) * 40
TEXT = "Merhaba, nasılsın? Yarın görüşürüz."
SCRATCH = tempfile.TemporaryDirectory()
pathlib.Path(SCRATCH.name, "syslog.py").write_text(SYSLOG)


def fresh():
    return tempfile.mkdtemp(dir=SCRATCH.name)


def cached(home):
    return [f for f in pathlib.Path(home).rglob("*") if f.is_file()]


def frame(obj):
    data = json.dumps(obj).encode()
    return struct.pack("=I", len(data)) + data


def run(stdin, fail="", stub=True, home=None):
    with tempfile.TemporaryDirectory() as tmp:
        log = pathlib.Path(tmp, "syslog.jsonl")
        env = {**os.environ, "PATH": tmp, "STUB_DIR": tmp, "STUB_FAIL": fail, "HOME": home or fresh(),
               "PYTHONPATH": SCRATCH.name, "SYSLOG_LOG": str(log)}
        if stub:
            pathlib.Path(tmp, "whisper-cli").write_text(STUB)
            pathlib.Path(tmp, "whisper-cli").chmod(0o755)
            env["PATH"] += f":{os.environ['PATH']}"
        p = subprocess.run([sys.executable, str(HOST)], input=stdin, capture_output=True, env=env, timeout=30)
        argv = json.loads(pathlib.Path(tmp, "argv.json").read_text()) if pathlib.Path(tmp, "argv.json").exists() else None
        sent = pathlib.Path(tmp, "stdin").read_bytes() if pathlib.Path(tmp, "stdin").exists() else None
        lines = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
    return p, argv, sent, lines


def line(lines):
    assert len(lines) == 1 and lines[0][0] == "voicenote", f"a note logged {lines}"
    assert "\n" not in lines[0][1], f"a log line spans lines: {lines[0][1]!r}"
    return lines[0][1]


def reply(p):
    out = p.stdout
    assert len(out) >= 4, f"no framed reply; exit {p.returncode}, stderr {p.stderr.decode()!r}"
    (n,) = struct.unpack("=I", out[:4])
    assert len(out) == 4 + n, f"reply framed as {n} bytes, {len(out) - 4} sent"
    return json.loads(out[4:])


MSG = frame({"wav": base64.b64encode(WAV).decode()})
home = fresh()
p, argv, sent, lines = run(MSG, home=home)
assert p.returncode == 0, p.stderr.decode()
assert argv is not None, "whisper-cli was not run"
# Without VAD, whisper-cli invents a line ("Altyazı M.K.") for a silent note.
for flag in (["-l", "tr"], ["-m", MODEL], ["-vm", VAD], ["-f", "-"]):
    i = argv.index(flag[0]) if flag[0] in argv else -1
    assert argv[i : i + 2] == flag, f"whisper-cli run without {' '.join(flag)}: {argv}"
assert "-nt" in argv, f"whisper-cli run without -nt: {argv}"
assert "--vad" in argv, f"whisper-cli run without --vad: {argv}"
assert "-otxt" in argv, f"whisper-cli run without -otxt: {argv}"
assert sent == WAV, "whisper-cli's stdin is not the sent WAV"
assert reply(p) == {"text": TEXT}, reply(p)
l = line(lines)
for part in ("0.3s cache=miss", "exit=0", "chars=35"):
    assert part in l, f"the first run logged {l!r}, without {part}"
assert "stderr=" not in l, f"a clean run logged stderr: {l!r}"
want = pathlib.Path(home, ".cache/voicenote", hashlib.sha256(WAV).hexdigest() + ".txt")
assert cached(home) == [want], f"the transcript was cached as {cached(home)}, not {want}"
assert want.read_text(encoding="utf-8") == TEXT

p, argv, _, lines = run(MSG, home=home)
assert argv is None, "a replayed note ran whisper-cli"
assert reply(p) == {"text": TEXT}, f"a replayed note replied {reply(p)}"
assert "cache=hit" in line(lines), f"a replayed note logged {lines}"

home = fresh()
p, _, _, lines = run(MSG, fail="silent", home=home)
assert reply(p) == {"error": "no speech heard"}, f"an empty transcript replied {reply(p)}"
assert "used without any other" in line(lines), f"an empty transcript logged no stderr: {lines}"
assert cached(home) == [], "an empty transcript was cached"

home = fresh()
p, _, _, lines = run(MSG, fail="loud", home=home)
r = reply(p)
assert set(r) == {"error"} and "failed to read audio data" in r["error"], f"a whisper-cli failure replied {r}"
l = line(lines)
assert "exit=2" in l and "stderr=whisper_init: loading model error: failed to read audio data" in l, f"a whisper-cli failure logged {l!r}"
assert cached(home) == [], "an error was cached"

# island.js would read an empty error as a transcript.
home = fresh()
p, _, _, lines = run(MSG, fail="quiet", home=home)
r = reply(p)
assert set(r) == {"error"} and r["error"], f"a whisper-cli failure with no stderr replied {r}"
assert "exit=3" in line(lines)
assert cached(home) == [], "an error was cached"

home = fresh()
pathlib.Path(home, ".cache").write_text("")
p, _, _, lines = run(MSG, home=home)
assert reply(p) == {"text": TEXT}, f"an unwritable cache replied {reply(p)}"
l = line(lines)
assert "cache=miss" in l and "cache_error=Not a directory" in l, f"an unwritable cache logged {l!r}"

p, _, _, lines = run(MSG, stub=False)
r = reply(p)
assert set(r) == {"error"} and r["error"], f"a missing whisper-cli replied {r}"
assert line(lines) == "0.3s cache=miss error=whisper-cli is not installed", lines

p, argv, _, lines = run(frame({"wav": "AAAA"})[:-3])
assert p.returncode != 0 and argv is None and p.stdout == b"", (p.returncode, argv, p.stdout)
assert lines == [], f"a message cut short logged {lines}"

print("voicenote-host OK")
