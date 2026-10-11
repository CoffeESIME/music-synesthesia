"use strict";

// YIN on a downsampled analysis window. Raw microphone audio stays on the device.
function detectMicrophoneNote(samples, sampleRate) {
    let energy = 0;
    for (const sample of samples) energy += sample * sample;
    if (Math.sqrt(energy / samples.length) < 0.008) return null;
    const half = Math.floor(samples.length / 2);
    const maxLag = Math.min(half - 1, Math.ceil(sampleRate / 65) + 1);
    const minLag = Math.max(2, Math.floor(sampleRate / 1500));
    const difference = new Float32Array(maxLag + 1);
    let total = 0;
    for (let lag = 1; lag <= maxLag; lag += 1) {
        let sum = 0;
        for (let i = 0; i < half; i += 1) {
            const delta = samples[i] - samples[i + lag];
            sum += delta * delta;
        }
        total += sum;
        difference[lag] = total > 0 ? sum * lag / total : 1;
        // A threshold crossing followed by a local minimum selects the fundamental.
        if (lag > minLag + 1 && difference[lag - 1] < 0.15
            && difference[lag] >= difference[lag - 1]) {
            const peak = lag - 1;
            const left = difference[peak - 1];
            const center = difference[peak];
            const right = difference[lag];
            const divisor = 2 * (2 * center - right - left);
            const offset = divisor === 0 ? 0 : (right - left) / divisor;
            const frequency = sampleRate / (peak + offset);
            const midi = Math.round(69 + 12 * Math.log2(frequency / 440));
            return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][((midi % 12) + 12) % 12];
        }
    }
    return null;
}

class BrowserMicrophone {
    constructor(onNote, onEnded) {
        this.onNote = onNote;
        this.onEnded = onEnded;
        this.running = false;
        this.starting = false;
        this.generation = 0;
        this.timer = null;
        this.stream = null;
        this.context = null;
        this.source = null;
    }

    async start() {
        if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
            throw new Error("El micrófono requiere HTTPS en la red local. Abre el enlace de acceso seguro que aparece debajo del botón.");
        }
        if (this.running || this.starting) return;
        const generation = ++this.generation;
        this.starting = true;
        try {
            this.context = new AudioContext();
            await this.context.resume();
            if (generation !== this.generation) return;
            const stream = await navigator.mediaDevices.getUserMedia({
                video: false,
                audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
            });
            if (generation !== this.generation) {
                stream.getTracks().forEach(track => track.stop());
                return;
            }
            this.stream = stream;
            this.source = this.context.createMediaStreamSource(stream);
            const analyser = this.context.createAnalyser();
            analyser.fftSize = 4096;
            this.source.connect(analyser);
            // No connection to destination: avoid playing the mic through the speakers.
            const raw = new Float32Array(analyser.fftSize);
            const step = Math.max(1, Math.floor(this.context.sampleRate / 12000));
            const samples = new Float32Array(Math.floor(raw.length / step));
            const rate = this.context.sampleRate / step;
            let candidate = null;
            let repetitions = 0;
            let previous = null;
            let silentWindows = 0;
            this.running = true;
            this.starting = false;
            const tick = () => {
                if (!this.running || generation !== this.generation) return;
                analyser.getFloatTimeDomainData(raw);
                for (let i = 0; i < samples.length; i += 1) {
                    let sum = 0;
                    for (let j = 0; j < step; j += 1) sum += raw[i * step + j];
                    samples[i] = sum / step;
                }
                const note = detectMicrophoneNote(samples, rate);
                repetitions = note && note === candidate ? repetitions + 1 : 1;
                candidate = note;
                silentWindows = note ? 0 : silentWindows + 1;
                if (note && repetitions >= 2 && note !== previous) {
                    previous = note;
                    this.onNote(note);
                } else if (silentWindows === 4) {
                    previous = null;
                    this.onNote(null);
                }
                this.timer = window.setTimeout(tick, 75);
            };
            stream.getAudioTracks().forEach(track => track.addEventListener("ended", () => {
                if (generation !== this.generation) return;
                this.stop();
                this.onEnded("El micrófono se desconectó o se retiró su permiso.");
            }));
            this.timer = window.setTimeout(tick, 75);
        } catch (error) {
            if (generation !== this.generation) return;
            this.stop();
            const messages = {
                NotAllowedError: "Permite el acceso al micrófono en los permisos de este sitio y vuelve a intentarlo.",
                NotFoundError: "Este dispositivo no tiene un micrófono disponible. Conecta uno y vuelve a intentarlo.",
                NotReadableError: "No se pudo abrir el micrófono. Revisa si otra aplicación lo está usando.",
            };
            throw new Error(messages[error.name] || error.message);
        }
    }

    stop() {
        this.generation += 1;
        this.running = false;
        this.starting = false;
        window.clearTimeout(this.timer);
        this.timer = null;
        this.stream?.getTracks().forEach(track => track.stop());
        this.source?.disconnect();
        void this.context?.close().catch(() => {});
        this.stream = null;
        this.source = null;
        this.context = null;
    }
}
