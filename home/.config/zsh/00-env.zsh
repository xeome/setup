export XDG_DATA_HOME="$HOME/.local/share"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_STATE_HOME="$HOME/.local/state"
export XDG_CACHE_HOME="$HOME/.cache"

export VISUAL="nvim"
export EDITOR="nvim"
export PAGER="most"
export LC_ALL="en_US.UTF-8"
export LANG="en_US.UTF-8"
export LANGUAGE="en_US.UTF-8"
export GPG_TTY="$(tty)"
export SSH_AUTH_SOCK="/run/user/$UID/rbw/ssh-agent-socket"
export SOPS_AGE_KEY_CMD="rbw get age-key"

export PARALLEL_HOME="$XDG_CONFIG_HOME/parallel"
export LESSHISTFILE="$XDG_CACHE_HOME/less/history"
export GHCUP_USE_XDG_DIRS="true"
export CARGO_HOME="$XDG_DATA_HOME/cargo"
export CMAKE_CXX_COMPILER_LAUNCHER="ccache"

typeset -U path PATH
path=(
    "$HOME/.local/bin"
    "$HOME/.local/bin/zig"
    "$HOME/.npm-global/bin"
    "$HOME/.opencode/bin"
    "/usr/local/go/bin"
    "$HOME/.cache/.bun/bin"
    "${path[@]}"
)

command -v go &>/dev/null && path+=("$(go env GOPATH)/bin")
[[ -d "$HOME/.local/share/junest/bin" ]] && path+=("$HOME/.local/share/junest/bin")

# Flutter and Android SDK live under XDG dirs on machines that have them;
# without these Gradle, Android and pub write ~/.gradle, ~/.android, ~/.pub-cache.
if [[ -d "$XDG_DATA_HOME/flutter/bin" ]]; then
    export ANDROID_HOME="$XDG_DATA_HOME/android-sdk"
    export ANDROID_USER_HOME="$XDG_DATA_HOME/android"
    export GRADLE_USER_HOME="$XDG_DATA_HOME/gradle"
    export PUB_CACHE="$XDG_CACHE_HOME/pub"
    path+=("$XDG_DATA_HOME/flutter/bin" "$ANDROID_HOME/cmdline-tools/latest/bin" "$PUB_CACHE/bin")
fi

export XDG_DATA_DIRS="/var/home/$USER/.local/share/flatpak/exports/share:/home/$USER/.local/share/flatpak/exports/share:/var/lib/flatpak/exports/share:/usr/local/share:/usr/share:/home/$USER/.local/share"
