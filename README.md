This is my personal repo for my Arch linux configurations.

# Layout

- `home/` is what chezmoi writes into `~` (`.chezmoiroot` points here).
- `infra/` is what lands outside `~`: packages and `/etc` drop-ins, deployed
  by pyinfra.
- `tools/` is never deployed: build scripts and tests, run from the repo.

The graphite palette is defined once, in `home/.chezmoidata/palette.toml`.
Every themed config is a chezmoi template that reads it. After changing
`ground`, `panel` or `raised`, run `tools/grain.py` to re-bake the grain
tiles. The boot console's colours in `infra/files/boot/cmdline` copy three
values by hand.

Zen's new tab and homepage are `home/dot_config/zen/hometab`, an unsigned
extension that `chezmoi apply` points every Zen profile at. Zen installs it
disabled: enable it once in the add-ons prompt, and disable any other new-tab
extension.

`home/dot_config/zen/voicenote` shows a local transcript of a Turkish
WhatsApp Web voice note while it plays, in a black island at the top of the
tab. The first deploy asks whether to install whisper-cpp and its 574 MB model,
and keeps the answer in `~/.local/state/dots/voicenote`. Delete that file to be
asked again on the next deploy, which runs when `infra/` changes. Until then the
extension stays linked or unlinked as it was. After a yes,
`chezmoi apply` links the extension into every Zen profile: enable it once in
the add-ons prompt, like the hometab. Its toolbar button turns transcribing on
and off, `journalctl -t voicenote` has a line for each note, and deleting
`~/.cache/voicenote` clears the cached transcripts.

To add a machine, give it a `[machines.<hostname>]` entry in
`home/.chezmoidata.toml`, then run `python3 -I tools/plymouth.py` and commit
its splash.

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
It runs on both compositors: `Compositor.qml.tmpl` picks the
`Quickshell.Hyprland` or `Quickshell.I3` backend from the machine's `wm`, and
nothing else in the shell knows which compositor it's on.

The packages, and everything this repo puts under `/etc`, come from one
[pyinfra](https://pyinfra.com) deploy, `infra/deploy.py`: the package names for
the machine's `wm`, and drop-ins for DNS, systemd-oomd, TLP profiles, polkit,
udev and the Qt environment. `chezmoi apply` runs it through `uvx` whenever a
file in `infra/` changes, so it needs `uv`, `yay` and `base-devel` first.
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

Incomplete but should get you most things.

```bash
chezmoi init https://github.com/xeome/setup
chezmoi apply -v
```

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
