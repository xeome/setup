// node tools/voicenote.test.mjs — checks home/dot_config/zen/voicenote's manifest, hook.js, wav.js,
// background.js and island.js.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import vm from "node:vm";

const DIR = new URL("../home/dot_config/zen/voicenote/", import.meta.url);
const read = name => readFileSync(new URL(name, DIR), "utf8");
const settle = () => new Promise(r => setImmediate(r));
const noTimer = () => { throw new Error("the island armed a timer"); };

function makeStorage(init = {}) {
    const data = { ...init }, listeners = [];
    return {
        local: {
            get: async key => (key in data ? { [key]: data[key] } : {}),
            set: async obj => {
                const changes = Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, { oldValue: data[k], newValue: v }]));
                Object.assign(data, obj);
                await null;
                for (const fn of listeners) fn(changes, "local");
            },
        },
        onChanged: { addListener: fn => listeners.push(fn) },
    };
}

function makeClock() {
    let now = 0, ids = 0;
    const timers = new Map();
    return {
        setTimeout: (fn, ms = 0) => { timers.set(++ids, { at: now + ms, fn }); return ids; },
        clearTimeout: id => { timers.delete(id); },
        advance(ms) {
            const end = now + ms;
            for (;;) {
                const [id, t] = [...timers].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at)[0] ?? [];
                if (!t) break;
                timers.delete(id);
                now = t.at;
                t.fn();
            }
            now = end;
        },
    };
}

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

async function loadBackground(storage = makeStorage()) {
    const badge = {}, sent = [], clicks = [], state = { native: { text: "merhaba" } };
    let onMessage;
    const ctx = vm.createContext({
        browser: {
            storage,
            browserAction: {
                setBadgeText: ({ text }) => { badge.text = text; },
                setTitle: ({ title }) => { badge.title = title; },
                onClicked: { addListener: fn => clicks.push(fn) },
            },
            runtime: {
                onMessage: { addListener: fn => { onMessage = fn; } },
                sendNativeMessage: (app, msg) => { sent.push({ app, msg: { ...msg } }); return Promise.resolve(state.native); },
            },
        },
        OfflineAudioContext: class {
            decodeAudioData() { return Promise.resolve({ duration: 12.5, length: 4 }); }
            createBufferSource() { return { connect() {}, start() {} }; }
            startRendering() { return Promise.resolve({ getChannelData: () => new Float32Array(4) }); }
        },
        // Node 22 has no Uint8Array.prototype.toBase64.
        wav: () => ({ toBase64: () => "V0FWIQ==" }),
    });
    vm.runInContext(read("background.js"), ctx);
    await settle();
    return {
        badge, sent, state,
        click: async () => { clicks.forEach(fn => fn()); await settle(); },
        message: async () => ({ ...(await onMessage({ blob: { arrayBuffer: async () => new ArrayBuffer(8) } })) }),
    };
}

function loadIsland(storage = makeStorage()) {
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
    const clock = makeClock();
    const sends = [];
    const copied = [];
    const window = target("window");
    const ctx = vm.createContext({
        window,
        document: { ...target("document"), documentElement: root, createElement: tag => new El(tag) },
        browser: { storage, runtime: { sendMessage: msg => new Promise((resolve, reject) => sends.push({ msg, resolve, reject })) } },
        navigator: { clipboard: { writeText: t => { copied.push(t); return Promise.resolve(); } } },
        setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout, setInterval: noTimer, requestAnimationFrame: noTimer,
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
    const buttons = () => island().children.filter(c => c.tagName === "BUTTON");
    const elements = (e = root) => [e, ...e.children.flatMap(c => elements(c))];
    return { listeners, sends, copied, play, esc, fire, island, view, root, clock, buttons, elements };
}

{
    const t = loadIsland();
    await settle();
    assert.equal(t.view(), null, "the island shows while idle");
    // Hover holds nothing, and nothing outside the island closes it.
    assert.deepEqual(t.listeners.map(l => `${l.name} ${l.type} capture=${l.capture}`).sort(),
        ["window keydown capture=true", "window message capture=false"]);
    t.play("blob:a");
    assert.deepEqual(t.elements().filter(e => Object.keys(e.handlers).length).map(e => `${e.tagName} ${Object.keys(e.handlers)}`),
        ["BUTTON click", "BUTTON click"], "an element handles more than a click on Copy and ×");
    assert.equal(t.sends.length, 1);
    assert.deepEqual(t.sends[0].msg.blob, { blobOf: "blob:a" }, "the blob was not sent to the background");
    assert.deepEqual(t.view(), { state: "pending", text: "transcribing" });
    t.sends[0].resolve({ text: "Merhaba, yarın görüşürüz." });
    await settle();
    assert.deepEqual(t.view(), { state: "text", text: "Merhaba, yarın görüşürüz." });

    const [copy, close] = t.buttons();
    copy.handlers.click.forEach(fn => fn({ stopPropagation() {} }));
    assert.deepEqual(t.copied, ["Merhaba, yarın görüşürüz."]);

    assert.equal(t.esc(), true);
    t.play("blob:a");
    assert.equal(t.sends.length, 1, "a replayed src was sent again");
    assert.deepEqual(t.view(), { state: "text", text: "Merhaba, yarın görüşürüz." });

    close.handlers.click.forEach(fn => fn({ stopPropagation() {} }));
    assert.equal(t.view(), null, "× left the island open");
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
    for (const type of ["pointerdown", "mousedown", "click"]) t.fire(type, { target: t.root });
    assert.notEqual(t.view(), null, "a click outside closed the island");
    assert.equal(t.esc(), true, "Esc was let through while the island showed");
    assert.equal(t.view(), null);
}

for (const [reply, view] of [
    [{ text: "uzun", seconds: 12 }, { state: "text", text: "uzun" }],
    [{ error: "no speech heard", seconds: 12 }, { state: "error", text: "no speech heard" }],
]) {
    const t = loadIsland();
    t.play("blob:a");
    t.clock.advance(60000);
    assert.deepEqual(t.view(), { state: "pending", text: "transcribing" }, "the pending pill closed on a timer");
    t.sends[0].resolve(reply);
    await settle();
    t.clock.advance(11999);
    assert.deepEqual(t.view(), view, `${JSON.stringify(reply)} closed before 12 s`);
    t.clock.advance(1);
    assert.equal(t.view(), null, `${JSON.stringify(reply)} stayed open at 12 s`);
}

for (const reply of [{ text: "kısa", seconds: 2 }, { text: "kısa" }]) {
    const t = loadIsland();
    t.play("blob:a");
    t.sends[0].resolve(reply);
    await settle();
    t.clock.advance(4999);
    assert.notEqual(t.view(), null, `${JSON.stringify(reply)} closed before 5 s`);
    t.clock.advance(1);
    assert.equal(t.view(), null, `${JSON.stringify(reply)} stayed open at 5 s`);
}

{
    const t = loadIsland();
    t.play("blob:a");
    t.sends[0].resolve({ text: "uzun", seconds: 12 });
    await settle();
    t.play("blob:b");
    t.clock.advance(13000);
    assert.deepEqual(t.view(), { state: "pending", text: "transcribing" }, "a result's timer closed the next note's pending pill");

    t.sends[1].resolve({ text: "ikinci", seconds: 12 });
    await settle();
    t.clock.advance(6000);
    assert.equal(t.esc(), true);
    t.play("blob:b");
    t.clock.advance(11999);
    assert.deepEqual(t.view(), { state: "text", text: "ikinci" }, "a replay from the Map closed before its 12 s");
    t.clock.advance(1);
    assert.equal(t.view(), null, "a replay from the Map did not arm its own 12 s");
}

{
    const t = loadIsland();
    t.play("blob:long");
    t.sends[0].resolve({ text: "otuz", seconds: 30 });
    await settle();
    t.esc();
    t.play("blob:short");
    t.sends[1].resolve({ text: "beş", seconds: 5 });
    await settle();
    t.play("blob:long");
    t.clock.advance(5000);
    assert.deepEqual(t.view(), { state: "text", text: "otuz" }, "a 5 s note's timer closed a 30 s replay");
    t.clock.advance(25000);
    assert.equal(t.view(), null);
}

{
    const storage = makeStorage();
    const bg = await loadBackground(storage);
    const t = loadIsland(storage);
    await settle();
    assert.deepEqual(bg.badge, { text: "", title: "voicenote: on" }, "the button is not on at a first start");
    await bg.click();
    assert.deepEqual(bg.badge, { text: "off", title: "voicenote: off" }, "one click did not turn it off");
    t.play("blob:a");
    assert.equal(t.sends.length, 0, "a play while off was sent");
    assert.equal(t.view(), null, "a play while off showed the island");
    await bg.click();
    assert.deepEqual(bg.badge, { text: "", title: "voicenote: on" }, "a second click did not turn it back on");
    t.play("blob:b");
    assert.equal(t.sends.length, 1, "a play after turning it back on was not sent once");
    assert.deepEqual(t.sends[0].msg.blob, { blobOf: "blob:b" });
}

{
    const storage = makeStorage({ off: true });
    const bg = await loadBackground(storage);
    const t = loadIsland(storage);
    await settle();
    assert.deepEqual(bg.badge, { text: "off", title: "voicenote: off" }, "a start with off stored shows on");
    t.play("blob:a");
    assert.equal(t.sends.length, 0, "an island started off sent a play");
    assert.equal(t.view(), null, "an island started off showed a play");
}

{
    const storage = makeStorage();
    const t = loadIsland(storage);
    await settle();
    t.play("blob:a");
    await storage.local.set({ off: true });
    await settle();
    t.play("blob:b");
    t.sends[0].resolve({ text: "ilk", seconds: 3 });
    await settle();
    assert.deepEqual(t.view(), { state: "text", text: "ilk" }, "the result in flight when turned off did not show");
    assert.equal(t.sends.length, 1, "a play while off was sent when the request in flight ended");

    t.esc();
    t.play("blob:a");
    assert.equal(t.view(), null, "a play while off of a src in the Map showed");
}

{
    const bg = await loadBackground();
    for (const native of [{ text: "merhaba" }, { error: "no speech heard" }]) {
        bg.state.native = native;
        assert.deepEqual(await bg.message(), { ...native, seconds: 12.5 }, `the background replied other than ${JSON.stringify(native)} plus seconds`);
    }
    assert.deepEqual(bg.sent.at(-1), { app: "xeome.voicenote", msg: { wav: "V0FWIQ==" } }, "the WAV did not reach the native host");
}

{
    const manifest = JSON.parse(read("manifest.json"));
    assert.ok(manifest.permissions.includes("storage"), "the manifest asks for no storage permission");
    assert.equal(manifest.browser_action?.default_area, "navbar", "the button would land in the extensions panel");
    // chezmoi deploys icon.svg.tmpl as icon.svg.
    const icon = manifest.browser_action.default_icon;
    assert.ok(existsSync(new URL(icon, DIR)) || existsSync(new URL(icon + ".tmpl", DIR)), "the button's icon is missing");
}

{
    const t = loadIsland();
    t.play("blob:a", { source: {} });
    t.play("blob:b", { type: "other" });
    assert.equal(t.sends.length, 0, "a foreign message was acted on");
    assert.equal(t.view(), null);
}

assert.doesNotMatch(read("hook.js"), /setTimeout|setInterval|requestAnimationFrame/, "hook.js arms a timer");
assert.doesNotMatch(read("island.js"), /customElements\.define\(/, "customElements is null in Firefox content scripts");

console.log("voicenote OK");
