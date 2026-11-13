// Runs in the page's own world (manifest: world MAIN), because only page code
// can fetch the blob: URL WhatsApp plays a voice note from. island.js picks the
// Blob up from the message. Videos and GIFs play from blob: URLs too, so only
// audio elements post.
(() => {
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function (...args) {
        const src = this.currentSrc || this.src;
        if (this instanceof HTMLAudioElement && src.startsWith("blob:")) {
            fetch(src)
                .then(r => r.blob())
                .then(blob => window.postMessage({ type: "xeome.voicenote", src, blob }, location.origin), () => {});
        }
        return play.apply(this, args);
    };
})();
