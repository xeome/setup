"""
Applies this repo to the machine it runs on: ~ from home/ (home.py), and
packages and /etc from deploy.py when what that half reads has changed.
~/.local/bin/dots runs it:

    cd ~/.local/share/dots/infra && uvx pyinfra@3.10.0 -y @local apply.py

Steps with a stamp under ~/.local/state/dots run again only when their inputs
changed (home.gates()), so an apply that changes nothing asks for no password
and writes nothing.
"""
import os
import pathlib
import shlex
import socket
import sys

# uvx puts its own Python first on PATH, and that one has no gi: qtct-conf and
# tools/kvantum.py need the system's. Set before any operation is declared,
# so every command they run sees it.
os.environ["PATH"] = os.pathsep.join(
    p for p in os.environ["PATH"].split(os.pathsep) if p != os.path.dirname(sys.executable))

from pyinfra import config, local  # noqa: E402
from pyinfra.operations import server  # noqa: E402

import home  # noqa: E402
from askonce import ask_once  # noqa: E402

HOME = pathlib.Path.home()
ROOT = home.ROOT
hostname = socket.gethostname()
assert hostname in home.data.MACHINES, f"{hostname} is not in MACHINES (infra/data.py)"
gates = home.gates(hostname)

# Kept out of the repo: .gitconfig and rbw's config read them from here.
ask_once(home.state(HOME) / "name", "Your name, for git commits?", text=True)
ask_once(home.state(HOME) / "email", "Your email, for git commits and Vaultwarden?", text=True)


def run(name, *argv):
    server.shell(name=name, commands=[shlex.join(map(str, argv))])


def system():
    config.SUDO = True
    local.include("deploy.py", data=home.data.system_inputs(hostname))
    config.SUDO = False


# First, so the steps below find their packages in the same apply.
home.gated("system", gates["system"], HOME, system)
# Before the home files and qt-theme, which read the gsettings it sets.
home.gated("set-theme", gates["set-theme"], HOME,
           lambda: run("GTK and icon themes", "bash", ROOT / "infra/scripts/set-theme.sh"))
if not (HOME / ".oh-my-zsh").is_dir():
    run("Install oh-my-zsh", "bash", ROOT / "infra/scripts/install-ohmyzsh.sh")

home.ops(home.plan(hostname, HOME, home.sources()))

# Generated rather than committed. It fetches its pinned KvLibadwaita into
# ~/.cache the first time, so that run needs the network.
home.gated("kvantum", gates["kvantum"], HOME,
           lambda: run("Build the Kvantum theme", "python3", "-I", ROOT / "tools/kvantum.py"))
home.gated("fonts", gates["fonts"], HOME,
           lambda: run("GTK fonts", "bash", ROOT / "infra/scripts/configure-fonts.sh",
                       home.data.MACHINES[hostname]["text_scale"]))

# Every apply: each of these does nothing when there is nothing to do.
run("qt5ct, qt6ct and Kvantum follow gsettings", ROOT / "home/.local/bin/qt-theme")
run("Import the git signing key", "bash", ROOT / "infra/scripts/import-gpg-key.sh")
run("Link Zen's profiles", "bash", ROOT / "infra/scripts/link-zen-chrome.sh")
