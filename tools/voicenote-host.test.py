#!/usr/bin/env python3
"""python3 -I tools/voicenote-host.test.py — checks home/dot_local/bin/executable_voicenote-host
against a stub whisper-cli on PATH, speaking Firefox's native messaging framing."""
import base64
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
# deploy.py downloads the model to this path, and the host must load it from there.
MODEL = re.search(r'^WHISPER_MODEL = "([^"]+)"', (ROOT / "infra/deploy.py").read_text(), re.M)[1]
host_model = re.search(r'^MODEL = "([^"]+)"', HOST.read_text(), re.M)[1]
assert host_model == MODEL, f"the host loads {host_model}, deploy.py downloads {MODEL}"
# Prints segments the way whisper-cli -nt does.
STUB = """#!/usr/bin/env python3
import json, os, sys
d = os.environ["STUB_DIR"]
open(os.path.join(d, "argv.json"), "w").write(json.dumps(sys.argv[1:]))
open(os.path.join(d, "stdin"), "wb").write(sys.stdin.buffer.read())
if os.environ.get("STUB_FAIL") == "quiet":
    sys.exit(3)
if os.environ.get("STUB_FAIL"):
    sys.stderr.write("whisper_init: loading model\\nerror: failed to read audio data\\n")
    sys.exit(2)
sys.stdout.write(" Merhaba, nasılsın?\\n Yarın görüşürüz.\\n")
"""
WAV = b"RIFF" + bytes(range(256)) * 40


def frame(obj):
    data = json.dumps(obj).encode()
    return struct.pack("=I", len(data)) + data


def run(stdin, fail="", stub=True):
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "PATH": tmp, "STUB_DIR": tmp, "STUB_FAIL": fail}
        if stub:
            pathlib.Path(tmp, "whisper-cli").write_text(STUB)
            pathlib.Path(tmp, "whisper-cli").chmod(0o755)
            env["PATH"] += f":{os.environ['PATH']}"
        p = subprocess.run([sys.executable, str(HOST)], input=stdin, capture_output=True, env=env, timeout=30)
        argv = json.loads(pathlib.Path(tmp, "argv.json").read_text()) if pathlib.Path(tmp, "argv.json").exists() else None
        sent = pathlib.Path(tmp, "stdin").read_bytes() if pathlib.Path(tmp, "stdin").exists() else None
    return p, argv, sent


def reply(p):
    out = p.stdout
    assert len(out) >= 4, f"no framed reply; exit {p.returncode}, stderr {p.stderr.decode()!r}"
    (n,) = struct.unpack("=I", out[:4])
    assert len(out) == 4 + n, f"reply framed as {n} bytes, {len(out) - 4} sent"
    return json.loads(out[4:])


p, argv, sent = run(frame({"wav": base64.b64encode(WAV).decode()}))
assert p.returncode == 0, p.stderr.decode()
assert argv is not None, "whisper-cli was not run"
for flag in (["-l", "tr"], ["-m", MODEL], ["-f", "-"]):
    i = argv.index(flag[0]) if flag[0] in argv else -1
    assert argv[i : i + 2] == flag, f"whisper-cli run without {' '.join(flag)}: {argv}"
assert "-nt" in argv, f"whisper-cli run without -nt: {argv}"
assert sent == WAV, "whisper-cli's stdin is not the sent WAV"
assert reply(p) == {"text": "Merhaba, nasılsın? Yarın görüşürüz."}, reply(p)

p, _, _ = run(frame({"wav": base64.b64encode(WAV).decode()}), fail="loud")
r = reply(p)
assert set(r) == {"error"} and "failed to read audio data" in r["error"], f"a whisper-cli failure replied {r}"

# island.js would read an empty error as a transcript.
p, _, _ = run(frame({"wav": base64.b64encode(WAV).decode()}), fail="quiet")
r = reply(p)
assert set(r) == {"error"} and r["error"], f"a whisper-cli failure with no stderr replied {r}"

p, _, _ = run(frame({"wav": base64.b64encode(WAV).decode()}), stub=False)
r = reply(p)
assert set(r) == {"error"} and r["error"], f"a missing whisper-cli replied {r}"

p, argv, _ = run(frame({"wav": "AAAA"})[:-3])
assert p.returncode != 0 and argv is None and p.stdout == b"", (p.returncode, argv, p.stdout)

print("voicenote-host OK")
