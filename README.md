This is my personal repo for my Arch linux configurations.

# Layout

- `home/` is what lands in `~`: every file sits at the path it has there. A
  `.j2` suffix marks a Jinja2 template, and git's own modes carry `+x` and
  symlinks. What a path cannot say is the manifest at the top of
  `infra/home.py`: the directories that hold nothing else, the private paths,
  the files a program rewrites.
- `infra/` is the deploy, one [pyinfra](https://pyinfra.com) run of
  `infra/apply.py`: `~` from `home/`, then packages and `/etc` drop-ins from
  `infra/deploy.py`.
- `tools/` is never deployed: build scripts and tests, run from the repo.

`infra/data.py` holds the graphite palette, the terminal colours and what
differs between machines, each once. Every themed config is a template that
reads it, the boot console's colours included, and `tools/data.test.py` fails
when one of its values is written out anywhere else. After changing `ground`,
`panel` or `raised`, run `tools/grain.py` to re-bake the grain tiles.

`dots` applies the repo. The repo wins over an edit made in `~`, so look
before applying over one:

| Command              | What it does                                         |
| -------------------- | ---------------------------------------------------- |
| `dots`               | Apply.                                               |
| `dots --dry --diff`  | Show what an apply would change.                     |
| `dots update`        | Pull, then apply.                                    |
| `cdots`              | `cd` to the repo.                                    |

A dry run changes nothing in `~` or `/etc`. It still asks the one-time
questions and keeps the answers.

In the repo, `just dry`, `just apply` and `just update` run the same commands,
even before the first apply has installed `dots`.

`just test` runs the default suite. Run `python3 -B infra/home.test.py` from
the repo root for the separate home regression check. Its pinned pyinfra
3.10.0 must already be in the uv cache. The check runs offline in a temporary
home. It does not apply changes to the live system.

An apply that changes nothing takes about half a second and asks for no
password: packages and `/etc` run again only when a file they read changed.
To run them regardless, delete `~/.local/state/dots/system.sha256`, then run
`dots`.

Zen's new tab and homepage are `home/.config/zen/hometab`, an unsigned
extension that every apply points each Zen profile at. Zen installs it
disabled: enable it once in the add-ons prompt, and disable any other new-tab
extension.

`home/.config/zen/voicenote` shows a local transcript of a Turkish
WhatsApp Web voice note while it plays, in a black island at the top of the
tab. The first deploy asks whether to install whisper-cpp and its 574 MB model,
and keeps the answer in `~/.local/state/dots/voicenote`. To be asked again,
delete that file and `~/.local/state/dots/system.sha256`, then run `dots`.
Until then the extension stays linked or unlinked as it was. After a yes, an
apply links the extension into every Zen profile: enable it once in the
add-ons prompt, like the hometab. Its toolbar button turns transcribing on and
off, `journalctl -t voicenote` has a line for each note, and deleting
`~/.cache/voicenote` clears the cached transcripts.

To add a machine, give its hostname an entry in `MACHINES` in
`infra/data.py`, then run `python3 -I tools/plymouth.py` and commit its
splash.

# Dependencies

| Type                       | Package(s)                                           |
| -------------------------- | ---------------------------------------------------- |
| WM                         | `hyprland`, or `swayfx` on machines set to sway      |
| Bar, notifications and OSD | `quickshell`                                         |
| Launcher                   | `vicinae`                                            |
| Terminal                   | `ghostty`                                            |
| Cursor                     | `Bibata-Modern-Classic`                              |
| Wallpaper                  | `waypaper`                                           |
| Lock screen                | `hyprlock`                                           |
| File manager               | `thunar`                                             |
| Screenshot tool            | quickshell `Shot` on hyprland, `flameshot` on sway   |
| Polkit manager             | `mate-polkit`                                        |
| Fonts                      | `inter-font ttf-jetbrains-mono-nerd`                 |
| Editor                     | `neovim`                                             |

One `quickshell` process draws the bar, the notification centre and the OSD.
It runs on both compositors: `Compositor.qml.j2` picks the
`Quickshell.Hyprland` or `Quickshell.I3` backend from the machine's `wm`, and
nothing else in the shell knows which compositor it's on.

The packages, and everything this repo puts under `/etc`, come from
`infra/deploy.py`: the package names for the machine's `wm`, and drop-ins for
DNS, systemd-oomd, TLP profiles, polkit, udev and the Qt environment.
Remove `power-profiles-daemon` before the first apply: `tlp-pd` conflicts with
it, and the unattended install answers no. On a machine missing AUR packages,
`yay` asks for the sudo password a second time. A package name deleted from
the deploy stays installed; its package table says how to remove one.

The deploy also themes the boot: a `plymouth` splash with the hostname in
dots, a graphite console palette on the kernel cmdline, and Ly's colours and
big clock. It only touches the boot on the dracut + kernel-install +
systemd-boot stack, and skips that section with a printed reason anywhere
else. If the splash ever hangs, press `e` in the boot menu and delete `splash`.
After adding a machine, run `tools/plymouth.py` to draw its wordmark.

# Installation

Needs `git`, `uv`, `yay` and `base-devel`, and the machine's hostname in
`MACHINES` (`infra/data.py`). The repo lives at `~/.local/share/dots`: the
`/etc` files and a few scripts name that path.

```bash
git clone https://github.com/xeome/setup ~/.local/share/dots
cd ~/.local/share/dots/infra
uvx pyinfra@3.10.0 -y @local apply.py
```

The first apply asks for the name and email git commits carry, and keeps them
in `~/.local/state/dots/`, outside the repo. After it, `~/.local/bin/dots`
applies the repo.

# Some shortcuts

Kept identical on both compositors, so muscle memory carries between machines.

| Shortcut          | Action                             |
| ----------------- | ---------------------------------- |
| Super + Return    | Launch terminal (`ghostty`)        |
| Super + E         | Launch file manager (`thunar`)     |
| Super + Q         | Launch web browser (`zen-browser`) |
| Super + R         | Launch app launcher (`vicinae`)    |
| Super + B         | Copy a reaction image              |
| Super + Shift + V | Clipboard history                  |
| Super + P         | Project sessionizer                |
| Super + L         | Lock screen (`hyprlock`)           |
| Super + K         | Toggle notification centre         |
| Super + T         | Toggle light and dark theme        |
| Super + Shift + C | Close focused window               |
| Super + Shift + R | Reload compositor config           |
| Super + arrows    | Focus window in that direction     |
| Super + 1-9 / 0   | Switch to workspace 1–10           |
| Print             | Screenshot                         |

The power menu has no keybind — it hangs off the battery module in the bar.
