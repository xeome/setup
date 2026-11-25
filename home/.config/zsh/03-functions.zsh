0short() { curl -F"shorten=$1" https://envs.sh; }
0file()  { curl -F"file=@$1" https://envs.sh; }

zst() {
    tar cf - "$1" | pv -s "$(du -sb "$1" | awk '{print $1}')" | zstd --adapt=min=6,max=19 -T0 >"$1.tar.zst"
}

jqi() {
    jq . "$1" > "tmp_$$.json" && mv "tmp_$$.json" "$1"
}

kb() { npx kanban-cli@0.3.1 "$@"; }

# Claude Code on Codex through CLIProxyAPI (cli-proxy-api.service). The token
# matches access.api-keys in ~/.config/cli-proxy-api/config.yaml. 272000 is
# gpt-6.2-astra's context, the smaller of the two models.
claudex() {
    ANTHROPIC_BASE_URL=http://127.0.0.1:18768 \
    ANTHROPIC_AUTH_TOKEN=unused \
    ANTHROPIC_MODEL='gpt-6.2-sol[1m]' \
    ANTHROPIC_DEFAULT_OPUS_MODEL='gpt-6.2-sol[1m]' \
    ANTHROPIC_DEFAULT_OPUS_MODEL_NAME='GPT-6.2 Sol' \
    ANTHROPIC_DEFAULT_SONNET_MODEL='gpt-6.2-sol[1m]' \
    ANTHROPIC_DEFAULT_SONNET_MODEL_NAME='GPT-6.2 Sol' \
    ANTHROPIC_DEFAULT_HAIKU_MODEL='gpt-6.2-sol[1m]' \
    ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME='GPT-6.2 Sol' \
    ANTHROPIC_DEFAULT_FABLE_MODEL='gpt-6.2-astra[1m]' \
    ANTHROPIC_DEFAULT_FABLE_MODEL_NAME='GPT-6.2 Astra' \
    ANTHROPIC_SMALL_FAST_MODEL='gpt-6.2-sol[1m]' \
    CLAUDE_CODE_AUTO_COMPACT_WINDOW=272000 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK=1 \
    CLAUDE_CODE_AUTO_MODE_SERVER=0 \
    CLAUDE_CODE_AUTO_MODE_MODEL='gpt-6.2-sol' \
        claude "$@"
}
