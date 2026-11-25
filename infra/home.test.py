"""Exercise apply.py's home operations with cached pyinfra and a temporary HOME."""
import json
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile

INFRA = pathlib.Path(__file__).resolve().parent
CACHE = pathlib.Path(os.environ.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache") / "uv"

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    home = root / "home"
    units = home / ".config/systemd/user"
    units.mkdir(parents=True)
    put, old, link = (units / name for name in ("new.service", "old.service", "alias.service"))
    other = home / ".config/systemd/user-local/other.service"
    other.parent.mkdir()
    log, order = root / "calls", root / "order"
    (home / ".oh-my-zsh").mkdir()
    state = home / ".local/state/dots"
    state.mkdir(parents=True)
    for key in ("name", "email"):
        (state / key).write_text("fixture\n")
    for rel in ("home/.local/bin/qt-theme", "infra/scripts/import-gpg-key.sh", "infra/scripts/link-zen-chrome.sh"):
        script = root / rel
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(f"#!/bin/sh\nprintf '%s\\n' {script.name} >> {shlex.quote(str(order))}\n")
        script.chmod(0o755)

    systemctl = root / "systemctl"
    systemctl.write_text(f'''#!{sys.executable}
import json, os, sys
from pathlib import Path

def read(path):
    p = Path(path)
    return os.readlink(p) if p.is_symlink() else p.read_text() if p.is_file() else None

with open({str(log)!r}, "a") as out:
    print(json.dumps([sys.argv[1:], [read(p) for p in {list(map(str, (put, old, link, other)))!r}]]), file=out)
with open({str(order)!r}, "a") as out:
    print("daemon-reload", file=out)
sys.exit(int(os.environ["FAIL_RELOAD"]))
''')
    systemctl.chmod(0o755)
    env = {**os.environ, "HOME": str(home), "PATH": f"{root}:{os.environ['PATH']}",
           "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR") or str(CACHE), "PYTHONDONTWRITEBYTECODE": "1"}
    deploy = root / "home_ops.py"

    def apply(label, actions, at_reload=None, *, fail_reload=False):
        log.write_text("")
        order.write_text("")
        actions = [(kind, str(path), payload, mode) for kind, path, payload, mode in actions]
        # Use the real apply order without including deploy.py or touching real scripts.
        deploy.write_text(f'''import pathlib, runpy, socket, sys
sys.path.insert(0, {str(INFRA)!r})
import home
home.ROOT = pathlib.Path({str(root)!r})
home.data.MACHINES[socket.gethostname()] = {{"text_scale": "fixture"}}
home.gates = lambda hostname: dict.fromkeys(("system", "set-theme", "kvantum", "releases", "fonts"))
home.gated = lambda *args: None
home.sources = lambda: []
home.plan = lambda *args: {actions!r}
runpy.run_path({str(INFRA / "apply.py")!r})
''')
        result = subprocess.run(["uvx", "--offline", "pyinfra@3.10.0", "-y", "@local", str(deploy)],
                                env={**env, "FAIL_RELOAD": str(int(fail_reload))}, cwd=root,
                                check=not fail_reload, capture_output=fail_reload, text=True)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        expected = [] if at_reload is None else [[['--user', 'daemon-reload'], at_reload]]
        assert calls == expected, f"{label}: expected systemctl calls {expected!r}, got {calls!r}"
        events = order.read_text().splitlines()
        if at_reload is not None:
            assert events[-1:] == ["daemon-reload"], f"{label}: reload did not run last: {events!r}"
            events = events[:-1]
        assert sorted(events) == ["import-gpg-key.sh", "link-zen-chrome.sh", "qt-theme"], events
        if fail_reload:
            output = result.stdout + result.stderr
            assert result.returncode != 0, f"{label}: apply unexpectedly succeeded\n{output}"
            assert "Run manually: systemctl --user daemon-reload" in output, f"{label}: recovery command missing\n{output}"

    put.write_text("before")
    old.write_text("retired")
    link.symlink_to("old.service")
    update = ("put", put, b"after", 0o644)
    delete = ("remove", old, None, None)
    relink = ("link", link, "new.service", None)
    unrelated = ("put", other, b"other", 0o644)
    apply("mixed batch", [delete, relink, update, unrelated], ["after", None, "new.service", "other"])
    apply("only a changed put", [("put", put, b"newer", 0o644)], ["newer", None, "new.service", "other"])
    apply("only a retired symlink", [("remove", link, None, None)], ["newer", None, None, "other"])
    apply("only a new symlink", [relink], ["newer", None, "new.service", "other"])
    apply("only a retired file", [("remove", put, None, None)], [None, None, "new.service", "other"])
    apply("only an unrelated put", [("put", other, b"new other", 0o644)])
    assert other.read_text() == "new other"
    stale, made = units / "old.service.d", units / "new"
    stale.mkdir()
    (stale / "override.conf").write_text("[Service]\nRestart=always\n")
    apply("only directory creation", [("dir", made, None, 0o755)])
    apply("only removal of a drop-in directory", [("remove", stale, None, None)],
          [None, None, "new.service", "new other"])
    assert made.is_dir() and not stale.exists()
    apply("only removal of an empty directory", [("remove", made, None, None)],
          [None, None, "new.service", "new other"])
    assert not made.exists()
    apply("no actions", [])
    apply("reload failure", [update], ["after", None, "new.service", "new other"], fail_reload=True)

print("home ops OK")
