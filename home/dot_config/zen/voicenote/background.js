// Decodes a voice note inside Firefox, so the sender's ogg/opus never reaches
// a native decoder, and hands 16 kHz mono WAV to the native host, which runs
// whisper-cli. Replies {text} or {error}, which island.js shows.
browser.runtime.onMessage.addListener(async ({ blob }) => {
    try {
        // decodeAudioData resamples to the context's rate; rendering downmixes to one channel.
        const decoded = await new OfflineAudioContext(1, 1, 16000).decodeAudioData(await blob.arrayBuffer());
        const ctx = new OfflineAudioContext(1, decoded.length, 16000);
        const source = ctx.createBufferSource();
        source.buffer = decoded;
        source.connect(ctx.destination);
        source.start();
        const mono = (await ctx.startRendering()).getChannelData(0);
        return await browser.runtime.sendNativeMessage("xeome.voicenote", { wav: wav(mono, 16000).toBase64() });
    } catch (e) {
        return { error: String(e?.message ?? e) };
    }
});
