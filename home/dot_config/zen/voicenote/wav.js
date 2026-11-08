// Mono float samples in [-1, 1] as a 16-bit PCM WAV file, the format
// whisper-cli reads from stdin.
function wav(samples, rate) {
    const v = new DataView(new ArrayBuffer(44 + samples.length * 2));
    const ascii = (at, s) => [...s].forEach((c, i) => v.setUint8(at + i, c.charCodeAt(0)));
    ascii(0, "RIFF");
    v.setUint32(4, 36 + samples.length * 2, true);
    ascii(8, "WAVEfmt ");
    v.setUint32(16, 16, true);       // fmt chunk size
    v.setUint16(20, 1, true);        // PCM
    v.setUint16(22, 1, true);        // channels
    v.setUint32(24, rate, true);
    v.setUint32(28, rate * 2, true); // bytes per second
    v.setUint16(32, 2, true);        // bytes per frame
    v.setUint16(34, 16, true);       // bits per sample
    ascii(36, "data");
    v.setUint32(40, samples.length * 2, true);
    samples.forEach((s, i) => {
        s = Math.max(-1, Math.min(1, s));
        v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    });
    return new Uint8Array(v.buffer);
}
