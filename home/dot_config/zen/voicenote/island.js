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
    let island, label, timer;
    // The toolbar button's state, which background.js keeps in storage.
    let off = false;
    browser.storage.local.get("off").then(r => { off = !!r.off; });
    browser.storage.onChanged.addListener((changes, area) => {
        if (area === "local" && "off" in changes) off = !!changes.off.newValue;
    });

    const hide = () => { island.hidden = true; };

    function build() {
        island = document.createElement("voicenote-island");
        label = document.createElement("voicenote-text");
        const copy = document.createElement("button");
        copy.textContent = "Copy";
        copy.addEventListener("click", () => navigator.clipboard.writeText(label.textContent));
        const close = document.createElement("button");
        close.textContent = "×";
        close.ariaLabel = "Close";
        close.addEventListener("click", hide);
        island.append(label, copy, close);
        document.documentElement.append(island);
    }

    function show(state, text, seconds) {
        if (!island) build();
        clearTimeout(timer);
        if (state !== "pending") timer = setTimeout(hide, Math.max(5, seconds || 0) * 1000);
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
                if (!r.error) texts.set(src, { text: r.text, seconds: r.seconds });
                if (src === newest) show(r.error ? "error" : "text", r.error ?? r.text, r.seconds);
                else if (!texts.has(newest)) send(newest, newestBlob);
            });
    }

    const shown = () => island && !island.hidden;

    window.addEventListener("message", e => {
        if (e.source !== window || e.data?.type !== "xeome.voicenote") return;
        if (off) return;
        ({ src: newest, blob: newestBlob } = e.data);
        const known = texts.get(newest);
        if (known) return show("text", known.text, known.seconds);
        show("pending", "transcribing");
        if (inFlight === null) send(newest, newestBlob);
    });

    // A click outside does not close it: pausing the note is one.
    window.addEventListener("keydown", e => {
        if (e.key !== "Escape" || !shown()) return;
        e.stopImmediatePropagation();
        e.preventDefault();
        hide();
    }, true);
})();
