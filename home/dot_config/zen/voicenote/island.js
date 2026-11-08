// The island: a black pill at the top of WhatsApp Web that shows the newest
// played voice note's transcript. Plain elements styled by island.css, which
// the manifest injects, so WhatsApp's CSP cannot block them. Not
// customElements.define: it is null in Firefox content scripts. Runs at
// document_start, so its Esc listener is on window before WhatsApp's.
// tools/voicenote.test.mjs checks it.
(() => {
    // Only transcripts are kept. An error is shown and forgotten, so a replay sends again.
    const texts = new Map();
    let newest = null, newestBlob = null, inFlight = null;
    let island, label;

    function build() {
        island = document.createElement("voicenote-island");
        label = document.createElement("voicenote-text");
        const copy = document.createElement("button");
        copy.textContent = "Copy";
        copy.addEventListener("click", () => navigator.clipboard.writeText(label.textContent));
        island.append(label, copy);
        document.documentElement.append(island);
    }

    function show(state, text) {
        if (!island) build();
        island.dataset.state = state;
        label.textContent = text;
        island.hidden = false;
    }

    // One request at a time, because each whisper-cli run loads a 574 MB model.
    // Notes skipped in between are sent only when replayed.
    function send(src, blob) {
        inFlight = src;
        browser.runtime.sendMessage({ blob })
            .then(r => r, err => ({ error: String(err?.message ?? err) }))
            .then(r => {
                inFlight = null;
                if (!r.error) texts.set(src, r.text);
                if (src === newest) show(r.error ? "error" : "text", r.error ?? r.text);
                else if (!texts.has(newest)) send(newest, newestBlob);
            });
    }

    const shown = () => island && !island.hidden;

    window.addEventListener("message", e => {
        if (e.source !== window || e.data?.type !== "xeome.voicenote") return;
        ({ src: newest, blob: newestBlob } = e.data);
        if (texts.has(newest)) return show("text", texts.get(newest));
        show("pending", "transcribing");
        if (inFlight === null) send(newest, newestBlob);
    });

    // Never on a timer: only Esc or a click outside closes it.
    window.addEventListener("keydown", e => {
        if (e.key !== "Escape" || !shown()) return;
        e.stopImmediatePropagation();
        e.preventDefault();
        island.hidden = true;
    }, true);
    window.addEventListener("pointerdown", e => {
        if (shown() && !island.contains(e.target)) island.hidden = true;
    }, true);
})();
