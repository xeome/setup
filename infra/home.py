"""
What this repo puts in ~. home/ holds every file at the path it has under ~,
a `.j2` suffix marks a Jinja2 template, and git's own modes carry +x and
symlinks. What a path alone cannot say is the manifest below.

plan() reads home/ and ~ and returns only what differs, so an apply that
changes nothing hands pyinfra no file op. ops() turns that into pyinfra
operations. The repo wins over an edit made in ~: `dots --dry --diff` shows
what an apply would overwrite.

    python3 -I infra/home.py   # self-check
"""
import base64
import filecmp
import hashlib
import io
import json
import os
import pathlib
import re
import runpy
import shlex
import stat
import subprocess
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
data = types.SimpleNamespace(**runpy.run_path(str(ROOT / "infra/data.py")))


def imports_managed(text):
    """vicinae's settings.json with chezmoi.json among its imports. The file is
    vicinae's own: its GUI rewrites it whole. It is JSONC, so it is edited as
    text, matched loosely enough for any spacing the GUI writes."""
    imports = re.search(r'"imports"\s*:\s*\[(\s*\])?', text)
    if '"chezmoi.json"' in text:
        return text
    if not text.strip():
        return '{\n   "imports": ["chezmoi.json"]\n}\n'
    if imports:
        # An empty list gets no trailing comma.
        entry = '"imports": ["chezmoi.json"]' if imports[1] else imports[0] + '"chezmoi.json", '
        return text[: imports.start()] + entry + text[imports.end():]
    # The first line that opens the object; the header above it is comments.
    lines = text.splitlines(keepends=True)
    i = next(n for n, line in enumerate(lines) if line.lstrip().startswith("{"))
    lines.insert(i + 1, '   "imports": ["chezmoi.json"],\n')
    return "".join(lines)


def enables_theme(text):
    """Vencord's settings.json with graphite.theme.css in enabledThemes, and
    nothing else changed. The file is Vencord's own: its GUI rewrites it and
    its cloud sync replaces it."""
    settings = json.loads(text) if text.strip() else {}
    themes = settings.setdefault("enabledThemes", [])
    if "graphite.theme.css" in themes:
        return text
    themes.append("graphite.theme.css")
    return json.dumps(settings, indent=4)


# Directories that hold only what home/ has for them: an apply deletes
# anything else it finds in one.
EXACT = {
    ".config/emoji", ".config/ghostty/themes", ".config/gtk-4.0", ".config/hypr/bin", ".config/hypr/lua_modules",
    ".config/mpv", ".config/mpv/fonts", ".config/mpv/script-opts", ".config/mpv/scripts", ".config/quickshell",
    ".config/quickshell/xeome", ".config/sway/conf.d", ".config/vesktop/themes", ".local/share/themes",
    ".local/share/themes/graphite-dark", ".local/share/themes/graphite-light", ".local/share/vicinae/themes",
}
PRIVATE = {
    ".config/alacritty/alacritty.toml", ".config/equibop", ".config/htop", ".config/htop/htoprc", ".config/mpv",
    ".config/rbw", ".config/rbw/config.json", ".config/vesktop", ".config/wtf/config.yml", ".local/share", ".ssh",
    ".ssh/config", ".ssh/config.d/01-globals.conf", ".ssh/controlmasters",
}
CREATE = {".config/hypr/user.local.lua"}
# Not written on a machine with this wm, and an exact directory under one of
# these keeps what it has. hyprlock is the lock screen on every machine, so
# hyprlock.conf and the bin/ scripts its labels call are not listed.
IGNORED = {
    "sway": (".config/hypr/hyprland.lua", ".config/hypr/user.local.lua", ".config/hypr/lua_modules"),
    "hyprland": (".config/sway",),
}
MERGES = {
    ".config/vicinae/settings.json": imports_managed,
    ".config/vesktop/settings/settings.json": enables_theme,
    # Equibop runs Equicord, a Vencord fork that keeps enabledThemes in the same place.
    ".config/equibop/settings/settings.json": enables_theme,
}
# Paths this repo once wrote and no longer has. Deleting a file from home/
# leaves it in ~ unless its directory is exact: list it here until every
# machine has applied.
RETIRED = ()


def sources(root=ROOT):
    """Every file under home/ that git tracks or would track, relative to it.
    From the repo root, because `git ls-files home/` run from infra/ lists
    nothing. A tracked file deleted from the working tree is left out."""
    # -z: without it git quotes a path that is not ASCII.
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "-co", "--exclude-standard", "home/"],
                         capture_output=True, text=True, check=True).stdout.split("\0")
    return [p.removeprefix("home/") for p in out if p and os.path.lexists(root / p)]


def renderer(hostname, home):
    import jinja2

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(ROOT / "infra/templates"),
                             undefined=jinja2.StrictUndefined, keep_trailing_newline=True)
    env.filters["quote"] = lambda v: json.dumps(str(v), ensure_ascii=False)
    env.globals.update(
        palette=data.PALETTE, term=data.TERMINAL, ansi=data.ansi, rgb=data.rgb, rgba=data.rgba, qt=data.qt,
        m=data.MACHINES[hostname], home=str(home), uid=os.getuid(),
        # Asked once per machine by apply.py.
        user=lambda key: (state(home) / key).read_text().strip(),
        b64=lambda path: base64.b64encode((ROOT / path).read_bytes()).decode(),
    )
    return lambda text: env.from_string(text).render().encode()


def plan(hostname, home, sources, tree=ROOT / "home"):
    """What an apply has to do to `home` for it to hold `sources`, the files
    under `tree`: a list of (kind, path, payload, mode).

        ("dir", path, None, mode)        make the directory, or fix its mode
        ("put", path, bytes | src, mode) write the file, or fix its mode
        ("link", path, target, None)
        ("remove", path, None, None)
    """
    if not sources:
        # Every file in an exact directory would be planned as a stray.
        raise ValueError("no sources: home/ lists no files")
    home, tree = pathlib.Path(home), pathlib.Path(tree)
    ignored = IGNORED[data.MACHINES[hostname]["wm"]]

    def skipped(rel):
        return any(rel == i or rel.startswith(i + "/") for i in ignored)

    def mode_of(path):
        return stat.S_IMODE(path.lstat().st_mode)

    render = renderer(hostname, home)
    wanted = {}
    for src in sources:
        rel = src.removesuffix(".j2")
        if not skipped(rel):
            wanted[rel] = tree / src
    wanted.update({rel: merge for rel, merge in MERGES.items() if not skipped(rel)})
    dirs = sorted({str(p) for rel in wanted for p in pathlib.PurePath(rel).parents if str(p) != "."})

    made, removed, linked, put = [], [], [], []
    for rel in dirs:
        mode = 0o700 if rel in PRIVATE else 0o755
        if not (home / rel).is_dir() or mode_of(home / rel) != mode:
            made.append(("dir", str(home / rel), None, mode))

    for rel, src in sorted(wanted.items()):
        dest = home / rel
        if rel in MERGES:
            now = dest.read_text() if dest.is_file() else ""
            new = src(now)
            payload, same = new.encode(), new == now and dest.is_file()
        elif src.is_symlink():
            target = os.readlink(src)
            if not dest.is_symlink() or os.readlink(dest) != target:
                linked.append(("link", str(dest), target, None))
            continue
        elif rel in CREATE and os.path.lexists(dest):
            continue
        elif src.suffix == ".j2":
            payload = render(src.read_text())
            same = dest.is_file() and dest.read_bytes() == payload
        else:
            payload = str(src)
            same = dest.is_file() and filecmp.cmp(src, dest, shallow=False)
        mode = 0o600 if rel in PRIVATE else 0o755 if not callable(src) and os.access(src, os.X_OK) else 0o644
        if dest.is_symlink() or dest.is_dir():
            # A put would follow the link and overwrite the file it points to,
            # or land inside the directory.
            removed.append(("remove", str(dest), None, None))
            same = False
        if not same or mode_of(dest) != mode:
            put.append(("put", str(dest), payload, mode))

    for rel in sorted(EXACT):
        if skipped(rel) or not (home / rel).is_dir():
            continue
        for name in sorted(os.listdir(home / rel)):
            child = f"{rel}/{name}"
            if child not in wanted and child not in dirs and not skipped(child):
                removed.append(("remove", str(home / child), None, None))
    removed += [("remove", str(home / rel), None, None) for rel in RETIRED if os.path.lexists(home / rel)]
    # A removal has to come before the put to the same path.
    return made + removed + linked + put


def ops(actions):
    from pyinfra.operations import files

    unit_dir = pathlib.Path.home() / ".config/systemd/user"
    reload_units = False
    for kind, path, payload, mode in actions:
        if kind == "dir":
            files.directory(name=path, path=path, mode=f"{mode:o}")
            continue
        if kind == "remove" and os.path.islink(path):
            files.link(name=f"Remove {path}", path=path, present=False)
        elif kind == "remove" and os.path.isdir(path):
            files.directory(name=f"Remove {path}", path=path, present=False)
        elif kind == "remove":
            files.file(name=f"Remove {path}", path=path, present=False)
        elif kind == "link":
            files.link(name=path, path=path, target=payload, force=True)
        else:
            # Explicit mode: the local connector copies from a 0600 temp file.
            files.put(name=path, src=io.BytesIO(payload) if isinstance(payload, bytes) else payload, dest=path,
                      mode=f"{mode:o}", create_remote_dir=False)
        if unit_dir in pathlib.Path(path).parents:
            reload_units = True
    return reload_units


def state(home):
    return pathlib.Path(home) / ".local/state/dots"


def gates(hostname):
    """{step: its inputs}. apply.py runs a gated step only when a byte of its
    inputs changed since the step last succeeded."""
    infra = ROOT / "infra"
    system = [infra / name for name in ("deploy.py", "cmdline.py", "askonce.py")]
    for path in sorted((infra / "files").rglob("*")):
        if path.is_file():
            system += [str(path.relative_to(infra)), path]
    return {
        # Everything the system half reads, and nothing else of data.py: a
        # change to the palette or to another machine asks for no password.
        "system": system + [repr(data.system_inputs(hostname))],
        "set-theme": [infra / "scripts/set-theme.sh"],
        "kvantum": [repr(data.PALETTE), ROOT / "tools/kvantum.py", ROOT / "home/.config/quickshell/xeome/grain-ground.png"],
        "fonts": [infra / "scripts/configure-fonts.sh", repr(data.MACHINES[hostname]["text_scale"])],
        "releases": [infra / "releases.toml", infra / "releases.py"],
    }


def stale(name, inputs, home):
    digest = hashlib.sha256()
    for i in inputs:
        digest.update(hashlib.sha256(i.read_bytes() if isinstance(i, pathlib.Path) else i.encode()).digest())
    stamp = state(home) / f"{name}.sha256"
    return None if stamp.is_file() and stamp.read_text() == digest.hexdigest() else digest.hexdigest()


def gated(name, inputs, home, step):
    """The stamp is an operation, not
    a write here: this runs while pyinfra plans, in a dry run too, and pyinfra
    stops at the first failed operation, so a failed step is never stamped."""
    from pyinfra.operations import server

    digest = stale(name, inputs, home)
    if digest:
        step()
        stamp = shlex.quote(str(state(home) / f"{name}.sha256"))
        server.shell(name=f"Stamp {name}", commands=[
            f"mkdir -p {shlex.quote(str(state(home)))} && printf %s {digest} > {stamp}"])


if __name__ == "__main__":
    import shutil
    import tempfile

    def do(actions):
        """What ops() has pyinfra do, done here, so each case can plan again."""
        for kind, dest, payload, mode in actions:
            dest = pathlib.Path(dest)
            if kind == "dir":
                dest.mkdir(exist_ok=True)
                dest.chmod(mode)
            elif kind == "put":
                dest.write_bytes(payload if isinstance(payload, bytes) else pathlib.Path(payload).read_bytes())
                dest.chmod(mode)
            elif kind == "link":
                dest.unlink(missing_ok=True)
                dest.symlink_to(payload)
            elif dest.is_dir() and not dest.is_symlink():
                shutil.rmtree(dest)
            else:
                dest.unlink()

    def kinds(actions):
        return sorted((kind, str(pathlib.Path(dest).relative_to(home))) for kind, dest, _, _ in actions)

    def mode(rel):
        return stat.S_IMODE((home / rel).lstat().st_mode)

    sway = next(h for h, m in data.MACHINES.items() if m["wm"] == "sway")
    hypr = next(h for h, m in data.MACHINES.items() if m["wm"] == "hyprland")
    # The manifest of a made-up tree, so the cases do not move when home/ does.
    EXACT, PRIVATE, CREATE, RETIRED = {"a", "wm/only"}, {"secret", "secret/key"}, {"once"}, ("old",)
    IGNORED = {"hyprland": ("wm",), "sway": ()}
    MERGES = {"merged/list": lambda text: text if "ours" in text else text + "ours\n"}

    with tempfile.TemporaryDirectory() as tmp:
        repo, home = pathlib.Path(tmp, "repo"), pathlib.Path(tmp, "home")
        tree = repo / "home"
        home.mkdir()
        files = {"a/kept": "kept\n", "a/çay": "a name git quotes\n", "a/tpl.j2": "{{ palette.dark.text }} {{ m.wm }} {{ rgba(palette.dark.line) }}\n",
                 "run": "#!/bin/sh\n", "once": "default\n", "wm/only/x": "x\n", "secret/key": "k\n"}
        for rel, text in files.items():
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            (tree / rel).write_text(text)
        (tree / "run").chmod(0o755)
        (tree / "link").symlink_to("a/kept")
        subprocess.run(["git", "init", "-q", repo], check=True)
        srcs = sources(repo)
        assert sorted(srcs) == sorted([*files, "link"]), srcs

        try:
            plan(sway, home, [], tree)
        except ValueError:
            pass
        else:
            raise AssertionError("an empty source list planned: every file in an exact dir would be a stray")

        do(plan(sway, home, srcs, tree))
        assert (home / "a/kept").read_text() == "kept\n"
        dark = data.PALETTE["dark"]
        assert (home / "a/tpl").read_text() == f"{dark['text']} sway rgba(255, 255, 255, 0.08)\n", (home / "a/tpl").read_text()
        assert not (home / "a/tpl.j2").exists()
        assert os.readlink(home / "link") == "a/kept"
        assert (home / "merged/list").read_text() == "ours\n"
        got = {rel: oct(mode(rel)) for rel in ("a", "a/kept", "run", "secret", "secret/key", "once")}
        want = {"a": "0o755", "a/kept": "0o644", "run": "0o755", "secret": "0o700", "secret/key": "0o600", "once": "0o644"}
        assert got == want, got
        assert plan(sway, home, srcs, tree) == [], f"a synced home still plans {kinds(plan(sway, home, srcs, tree))}"

        (home / "a/stray").write_text("s")
        (home / "a/straydir").mkdir()
        (home / "a/straydir/x").write_text("s")
        actions = plan(sway, home, srcs, tree)
        assert kinds(actions) == [("remove", "a/stray"), ("remove", "a/straydir")], kinds(actions)
        do(actions)
        assert sorted(p.name for p in (home / "a").iterdir()) == ["kept", "tpl", "çay"]

        (home / "wm/only/stray").write_text("s")
        (home / "wm/only/x").write_text("edited")
        # (a/tpl renders the wm, so the other machine has that one file to write.)
        assert kinds(plan(hypr, home, srcs, tree)) == [("put", "a/tpl")], kinds(plan(hypr, home, srcs, tree))
        assert kinds(plan(sway, home, srcs, tree)) == [("put", "wm/only/x"), ("remove", "wm/only/stray")]
        do(plan(sway, home, srcs, tree))

        (home / "once").write_text("mine")
        assert plan(sway, home, srcs, tree) == []
        assert (home / "once").read_text() == "mine"

        (home / "merged/list").write_text("theirs\n")
        do(plan(sway, home, srcs, tree))
        assert (home / "merged/list").read_text() == "theirs\nours\n"
        assert plan(sway, home, srcs, tree) == []

        (home / "old").write_text("retired")
        actions = plan(sway, home, srcs, tree)
        assert kinds(actions) == [("remove", "old")], kinds(actions)
        do(actions)
        assert not (home / "old").exists()

        # A link pointed elsewhere, as `systemctl --user enable` leaves one.
        (home / "link").unlink()
        (home / "link").symlink_to("/elsewhere")
        actions = plan(sway, home, srcs, tree)
        assert kinds(actions) == [("link", "link")], kinds(actions)
        do(actions)
        assert os.readlink(home / "link") == "a/kept"

        (home / "a/kept").chmod(0o600)
        (home / "secret").chmod(0o755)
        (home / "run").write_text("edited")
        (home / "link").unlink()
        (home / "link").write_text("a file now")
        (home / "secret/key").unlink()
        (home / "secret/key").symlink_to("../a/kept")
        actions = plan(sway, home, srcs, tree)
        want = [("dir", "secret"), ("link", "link"), ("put", "a/kept"), ("put", "run"), ("put", "secret/key"), ("remove", "secret/key")]
        assert kinds(actions) == want, kinds(actions)
        do(actions)
        assert (oct(mode("a/kept")), oct(mode("secret")), oct(mode("run"))) == ("0o644", "0o700", "0o755")
        assert (home / "run").read_text() == "#!/sh\n".replace("/sh", "/bin/sh") and os.readlink(home / "link") == "a/kept"
        assert not (home / "secret/key").is_symlink() and (home / "a/kept").read_text() == "kept\n", "a put wrote through a link"
        assert plan(sway, home, srcs, tree) == []

        one = stale("step", [tree / "run", "text"], home)
        assert one and stale("step", [tree / "run", "text"], home) == one
        (home / ".local/state/dots").mkdir(parents=True)
        (home / ".local/state/dots/step.sha256").write_text(one)
        assert stale("step", [tree / "run", "text"], home) is None
        assert stale("step", [tree / "run", "other"], home) not in (None, one)
        (tree / "run").write_text("#!/bin/sh\nchanged\n")
        assert stale("step", [tree / "run", "text"], home) not in (None, one)
    print("home OK")
