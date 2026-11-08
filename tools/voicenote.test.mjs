// node tools/voicenote.test.mjs — checks home/dot_config/zen/voicenote's hook.js, wav.js and island.js.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const DIR = new URL("../home/dot_config/zen/voicenote/", import.meta.url);
const read = name => readFileSync(new URL(name, DIR), "utf8");
const settle = () => new Promise(r => setImmediate(r));
const noTimer = () => { throw new Error("the island armed a timer"); };

{
    const returned = [];
    class HTMLMediaElement {
        constructor(src) { this.src = src; this.currentSrc = ""; }
        play() { const r = { from: "original play" }; returned.push(r); return r; }
    }
    class HTMLAudioElement extends HTMLMediaElement {}
    class HTMLVideoElement extends HTMLMediaElement {}
    const posts = [];
    const ctx = vm.createContext({
        HTMLMediaElement, HTMLAudioElement, HTMLVideoElement,
        location: { origin: "https://web.whatsapp.com" },
        fetch: url => Promise.resolve({ blob: () => Promise.resolve({ blobOf: url }) }),
        postMessage: (data, origin) => posts.push({ data, origin }),
    });
    ctx.window = ctx;
    vm.runInContext(read("hook.js"), ctx);

    const note = new HTMLAudioElement("blob:https://web.whatsapp.com/1111");
    const r = note.play();
    assert.equal(r, returned.at(-1), "play() did not return the original play's result");
    await settle();
    assert.equal(posts.length, 1, "an audio blob: play posted nothing");
    assert.equal(posts[0].data.type, "xeome.voicenote");
    assert.equal(posts[0].data.src, "blob:https://web.whatsapp.com/1111");
    assert.deepEqual(posts[0].data.blob, { blobOf: "blob:https://web.whatsapp.com/1111" });
    assert.equal(posts[0].origin, "https://web.whatsapp.com");

    new HTMLVideoElement("blob:https://web.whatsapp.com/2222").play();
    new HTMLAudioElement("https://web.whatsapp.com/ding.mp3").play();
    await settle();
    assert.equal(posts.length, 1, "a video blob: or an https audio src posted");
}

{
    const ctx = vm.createContext({});
    vm.runInContext(read("wav.js"), ctx);
    const bytes = ctx.wav(new Float32Array([0, 1, -1, 0.5, -0.5, 2]), 16000);
    assert.ok(ArrayBuffer.isView(bytes), "wav() did not return bytes");
    const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const str = (o, n) => String.fromCharCode(...new Uint8Array(bytes.buffer, bytes.byteOffset + o, n));
    assert.equal(bytes.byteLength, 44 + 12);
    assert.equal(str(0, 4), "RIFF");
    assert.equal(v.getUint32(4, true), 36 + 12);
    assert.equal(str(8, 8), "WAVEfmt ");
    assert.deepEqual(
        [v.getUint32(16, true), v.getUint16(20, true), v.getUint16(22, true), v.getUint32(24, true),
         v.getUint32(28, true), v.getUint16(32, true), v.getUint16(34, true)],
        [16, 1, 1, 16000, 32000, 2, 16],
        "fmt chunk: size, PCM, channels, rate, byte rate, block align, bits",
    );
    assert.equal(str(36, 4), "data");
    assert.equal(v.getUint32(40, true), 12);
    assert.deepEqual([0, 1, 2, 3, 4, 5].map(i => v.getInt16(44 + i * 2, true)), [0, 32767, -32768, 16383, -16384, 32767]);
}

function loadIsland() {
    const listeners = [];
    const target = name => ({
        addEventListener: (type, fn, opt) => listeners.push({ name, type, fn, capture: opt === true || opt?.capture === true }),
    });
    class El {
        constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.parent = null; this.hidden = false; this.textContent = ""; this.dataset = {}; this.handlers = {}; }
        append(...cs) { for (const c of cs) { c.parent = this; this.children.push(c); } }
        appendChild(c) { this.append(c); return c; }
        contains(n) { for (; n; n = n.parent) if (n === this) return true; return false; }
        addEventListener(type, fn) { (this.handlers[type] ??= []).push(fn); }
        find(tag) { return this.tagName === tag ? this : this.children.map(c => c.find(tag)).find(Boolean); }
    }
    const root = new El("html");
    const sends = [];
    const copied = [];
    const window = target("window");
    const ctx = vm.createContext({
        window,
        document: { ...target("document"), documentElement: root, createElement: tag => new El(tag) },
        browser: { runtime: { sendMessage: msg => new Promise((resolve, reject) => sends.push({ msg, resolve, reject })) } },
        navigator: { clipboard: { writeText: t => { copied.push(t); return Promise.resolve(); } } },
        setTimeout: noTimer, setInterval: noTimer, requestAnimationFrame: noTimer,
    });
    vm.runInContext(read("island.js"), ctx);

    const fire = (type, event) => {
        for (const l of listeners.filter(l => l.name === "window" && l.type === type)) l.fn(event);
    };
    const play = (src, { source = window, type = "xeome.voicenote" } = {}) =>
        fire("message", { source, data: { type, src, blob: { blobOf: src } } });
    const esc = () => {
        const e = { key: "Escape", stopped: false, stopPropagation() { this.stopped = true; }, stopImmediatePropagation() { this.stopped = true; }, preventDefault() {} };
        fire("keydown", e);
        return e.stopped;
    };
    const island = () => root.find("VOICENOTE-ISLAND");
    const view = () => {
        const el = island();
        return el && !el.hidden ? { state: el.dataset.state, text: el.find("VOICENOTE-TEXT").textContent } : null;
    };
    return { listeners, sends, copied, play, esc, fire, island, view, root };
}

{
    const t = loadIsland();
    assert.equal(t.view(), null, "the island shows while idle");
    for (const type of ["keydown", "pointerdown"]) {
        const l = t.listeners.find(l => l.type === type);
        assert.ok(l && l.name === "window" && l.capture, `${type} is not caught on window in the capture phase`);
    }
    t.play("blob:a");
    assert.equal(t.sends.length, 1);
    assert.deepEqual(t.sends[0].msg.blob, { blobOf: "blob:a" }, "the blob was not sent to the background");
    assert.deepEqual(t.view(), { state: "pending", text: "transcribing" });
    t.sends[0].resolve({ text: "Merhaba, yarın görüşürüz." });
    await settle();
    assert.deepEqual(t.view(), { state: "text", text: "Merhaba, yarın görüşürüz." });

    const copy = t.island().find("BUTTON");
    copy.handlers.click.forEach(fn => fn({ stopPropagation() {} }));
    assert.deepEqual(t.copied, ["Merhaba, yarın görüşürüz."]);

    assert.equal(t.esc(), true);
    t.play("blob:a");
    assert.equal(t.sends.length, 1, "a replayed src was sent again");
    assert.deepEqual(t.view(), { state: "text", text: "Merhaba, yarın görüşürüz." });
}

{
    const t = loadIsland();
    t.play("blob:a");
    t.play("blob:b");
    t.play("blob:c");
    assert.equal(t.sends.length, 1, "a play was sent while another request was in flight");
    assert.deepEqual(t.view(), { state: "pending", text: "transcribing" });
    t.sends[0].resolve({ text: "eski" });
    await settle();
    assert.deepEqual(t.view(), { state: "pending", text: "transcribing" }, "an older src's reply was shown");
    assert.equal(t.sends.length, 2, "the newest src was not sent when the request in flight ended");
    assert.deepEqual(t.sends[1].msg.blob, { blobOf: "blob:c" }, "a skipped src was sent instead of the newest");

    assert.equal(t.esc(), true);
    assert.equal(t.view(), null, "Esc did not dismiss the island");
    t.sends[1].resolve({ text: "yeni" });
    await settle();
    assert.deepEqual(t.view(), { state: "text", text: "yeni" }, "the newest src's reply left a dismissed island closed");
    assert.equal(t.sends.length, 2, "a skipped src was sent with no replay");

    t.play("blob:a");
    assert.deepEqual(t.view(), { state: "text", text: "eski" }, "the stored older reply was lost");
    assert.equal(t.sends.length, 2);
    t.play("blob:b");
    assert.equal(t.sends.length, 3, "a skipped src was not sent on its replay");
}

{
    const t = loadIsland();
    t.play("blob:a");
    t.sends[0].resolve({ error: "whisper-cli: failed to read audio" });
    await settle();
    assert.deepEqual(t.view(), { state: "error", text: "whisper-cli: failed to read audio" });
    assert.equal(t.sends.length, 1, "an error was sent again with no replay");
    t.play("blob:b");
    t.sends[1].reject(new Error("No such native application xeome.voicenote"));
    await settle();
    assert.equal(t.view().state, "error");
    assert.match(t.view().text, /No such native application/);

    t.play("blob:a");
    assert.equal(t.sends.length, 3, "a replay after an error was not sent again");
    assert.deepEqual(t.view(), { state: "pending", text: "transcribing" }, "a replay after an error showed the stale error");
}

{
    const t = loadIsland();
    assert.equal(t.esc(), false, "Esc was stopped while the island was hidden");
    t.play("blob:a");
    t.fire("pointerdown", { target: t.island().find("VOICENOTE-TEXT") });
    assert.notEqual(t.view(), null, "a click inside dismissed the island");
    t.fire("pointerdown", { target: t.root });
    assert.equal(t.view(), null, "a click outside left the island open");
    assert.equal(t.esc(), false, "Esc was stopped after a click outside hid the island");
    t.play("blob:b");
    assert.equal(t.esc(), true, "Esc was let through while the island showed");
    assert.equal(t.view(), null);
}

{
    const t = loadIsland();
    t.play("blob:a", { source: {} });
    t.play("blob:b", { type: "other" });
    assert.equal(t.sends.length, 0, "a foreign message was acted on");
    assert.equal(t.view(), null);
}

for (const name of ["island.js", "hook.js"]) {
    assert.doesNotMatch(read(name), /setTimeout|setInterval|requestAnimationFrame/, `${name} arms a timer`);
}
assert.doesNotMatch(read("island.js"), /customElements\.define\(/, "customElements is null in Firefox content scripts");

console.log("voicenote OK");
