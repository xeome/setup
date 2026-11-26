"""
The one copy of the graphite palette, the terminal colours and what differs
between machines. home.py renders the templates in home/ from it, apply.py
gates the system half on system_inputs(), and tools/ reads it too.

Every reader loads this file by path, because `python3 -I` drops the script's
own directory from sys.path. tools/data.test.py fails when a value here is
written out anywhere else in the repo.
"""

# The graphite palette (the graphite-ui skill). Opaque colours are #rrggbb,
# translucent ones #rrggbbaa. rgb(), rgba() and qt() below write them in the
# notations other programs want.
PALETTE = {
    "dark": {
        # Grounds: the bar is `ground`, everything floating is `raised`, and
        # `panel` is a window's background (terminals, GTK views, the desk's tiles).
        "ground": "#0a0a0c",
        "panel": "#0e0e10",
        "raised": "#151618",
        "rule": "#232427",  # slider troughs

        # Two tones carry hierarchy: bright for titles and values, dim for labels
        # and metadata. text is everything else that is read, not scanned.
        "text": "#e6e7ea",
        "bright": "#f7f8f8",
        "dim": "#8a8f98",

        # Colour is spent on meaning only. warm is focus and a live microphone,
        # hot is something that wants you (low battery, urgent workspace, a
        # critical notification). Selection is not a colour: it is `sel`.
        "warm": "#e5ae52",
        "hot": "#e2715a",
        "success": "#b5c98f",  # status only: GTK and vicinae

        # Every edge is two lines: `line` one pixel in, `ring` as the outer pixel.
        "line": "#ffffff14",
        "ring": "#0000004d",
        "focus": "#ffffff80",  # the focused window's border (hyprland, sway)
        "lift": "#ffffff0d",  # a card's top edge
        "card": "#ffffff05",  # bar modules: nearly clear
        "hover": "#ffffff0d",
        "sel": "#ffffff12",

        # Corner glow, colourless and gone within a few hundred pixels.
        "glow": "#ffffff0d",  # the bar
        "glowPanel": "#ffffff11",  # raised, top-left
        "glowPanelFar": "#ffffff08",  # raised, top-right

        # line, hover and sel composited over a ground, for programs that draw
        # alpha as solid (vicinae). Recompute them when those tokens change.
        "flat": {
            "line": "#1d1d1f",  # over ground
            "hover": "#161618",  # over ground
            "sel": "#1b1b1d",  # over ground
            "hoverRaised": "#212224",
        },
    },
    "light": {
        "ground": "#ededef",
        "panel": "#f8f8f9",
        "raised": "#ffffff",
        "rule": "#cfcfd3",
        "text": "#26272b",
        "bright": "#0f1011",
        "dim": "#62666d",
        "warm": "#885b0c",
        "hot": "#af3a1e",
        "success": "#276d77",
        "line": "#00000017",
        "ring": "#0000000a",
        "lift": "#ffffffcc",
        "card": "#ffffff80",
        "hover": "#0000000a",
        "sel": "#0000000e",
        "glow": "#ffffffb3",
        "glowPanel": "#ffffffe6",
        "glowPanelFar": "#ffffff66",
    },
}
_DARK = PALETTE["dark"]

# The terminals' colours (ghostty, alacritty, foot), Caffeine's hues:
# https://github.com/crynta/terax-ai src/modules/theme/themes/caffeine.ts
# Dark's black is `rule`, not a true black, because the background is already
# near-black.
TERMINAL = {
    "dark": {
        "normal": {"black": _DARK["rule"], "red": "#e06c75", "green": "#b5c98f", "yellow": "#ffd9a0",
                   "blue": "#8fb0d9", "magenta": "#cba6c9", "cyan": "#88c0c8", "white": _DARK["text"]},
        "bright": {"black": _DARK["dim"], "red": "#ff8a93", "green": "#c9dba8", "yellow": "#ffe6c4",
                   "blue": "#a9c3e0", "magenta": "#ddc0db", "cyan": "#a4d4da", "white": _DARK["bright"]},
    },
    # Caffeine's `variants.light`.
    "light": {
        "normal": {"black": "#3a322a", "red": "#c0392b", "green": "#5a7d3c", "yellow": "#a9762a",
                   "blue": "#3a6ea5", "magenta": "#9a4f8a", "cyan": "#2a8589", "white": "#c8c0b4"},
        "bright": {"black": "#6b6258", "red": "#d04a3a", "green": "#6a9048", "yellow": "#c08a3a",
                   "blue": "#4a7eb5", "magenta": "#aa5f9a", "cyan": "#3a989c", "white": "#202020"},
        "background": "#f9f9f9",
        "foreground": "#202020",
        "cursor": "#644a40",
        "cursorText": "#ffffff",
        # The cursor colour as a 16% wash, flattened over the background.
        "selection": "#e1dddb",
    },
}


def ansi(mode):
    return [*TERMINAL[mode]["normal"].values(), *TERMINAL[mode]["bright"].values()]


# The boot console's 16 colours, set on the kernel cmdline. Slots 1-6 are the
# console's own, darker than the terminals'; 7-15 are the terminals'.
CONSOLE = ["#000000", "#b8585f", "#6e7a56", "#887353", "#607894", "#876e86", "#567c81", *ansi("dark")[7:]]

# What differs between machines. Every machine must be listed: there is no
# default. Laptop or desktop is left out: infra/deploy.py asks hostnamectl.
#
#   wm          hyprland or sway: picks the compositor config and its packages.
#   lock_output the output hyprlock puts its input field, player and system info on.
#   text_scale  multiplies GTK and quickshell text; terminals stay at 10pt.
#   monitors    each output, and the workspaces it holds.
MACHINES = {
    "xeome-desktop": {
        "wm": "hyprland",
        "lock_output": "DP-3",
        # 1.1 is a compromise for the 27" 1440p at 65 cm: 1.35 reached the 12'
        # x-height reading floor but looked too big. The ultrabook gets there
        # through monitor scale 2, so its text stays at 1.
        "text_scale": 1.1,
        "monitors": [
            {"output": "HDMI-A-1", "mode": "2560x1440@75", "position": "0x0", "scale": 1, "workspaces": [1, 4]},
            {"output": "DP-3", "mode": "1920x1080@144", "position": "2560x360", "scale": 1,
             "workspaces": [2, 3, 5, 6, 7, 8, 9]},
        ],
    },
    "emin-ultrabook": {
        "wm": "hyprland",
        "lock_output": "eDP-1",
        "text_scale": 1,
        "monitors": [
            {"output": "DP-3", "mode": "3840x2160@60", "position": "0x0", "scale": 2, "workspaces": [2, 4, 5, 6]},
            {"output": "eDP-1", "mode": "1920x1200@60", "position": "0x1080", "scale": 1,
             "workspaces": [1, 3, 7, 8, 9]},
        ],
    },
    # HP ProBook running swayfx, docked to an HP E24 G4. eDP-1 sits left of the
    # external. Undocking is safe: sway ignores output directives for outputs
    # that aren't connected, and HDMI-A-1's workspaces fall back to the only
    # screen left.
    "emin-probook": {
        "wm": "sway",
        "lock_output": "eDP-1",
        "text_scale": 1,
        "monitors": [
            {"output": "eDP-1", "mode": "1920x1080@60", "position": "0x0", "scale": 1, "workspaces": [1, 3]},
            {"output": "HDMI-A-1", "mode": "1920x1080@60", "position": "1920x0", "scale": 1,
             "workspaces": [2, 4, 5, 6, 7, 8, 9]},
        ],
    },
}


def channels(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def rgb(h):
    return ", ".join(map(str, channels(h)))


def rgba(h):
    return f"rgba({rgb(h)}, {round(int(h[7:9] or 'ff', 16) / 255, 2):g})"


def qt(h):
    """"#rrggbbaa" or "#rrggbb" -> "#AARRGGBB", the order Qt reads."""
    return f"#{h[7:9] or 'ff'}{h[1:7]}".upper()


def system_inputs(hostname):
    """All the system half (infra/deploy.py) reads from this file. apply.py
    runs that half again when this changes, and only then."""
    m = MACHINES[hostname]
    vt = [f"vt.default_{name}=" + ",".join(str(channels(c)[i]) for c in CONSOLE)
          for i, name in enumerate(("red", "grn", "blu"))]
    return {"hostname": hostname, "wm": m["wm"], "vt": vt}
