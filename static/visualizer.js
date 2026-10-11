"use strict";

// An artistic nodal-field model driven by pitch class, not a physical plate solver.
// It deliberately uses the same note events as the lights, without opening audio.
class NoteVisualizer {
    constructor(canvas, stage, motionPreference) {
        this.canvas = canvas;
        this.stage = stage;
        this.context = canvas.getContext("2d", { alpha: false });
        this.motionPreference = motionPreference;
        this.mode = "cymatic";
        this.note = null;
        this.color = "#D9D2C3";
        this.running = false;
        this.paused = false;
        this.frame = null;
        this.lastTime = 0;
        this.phase = 0;
        this.count = 14000;
        this.points = new Float32Array(this.count * 2);
        this.targets = null;
        this.cache = new Map();
        this.available = Boolean(this.context);
        if (!this.available) return;

        this.resizeObserver = new ResizeObserver(() => this.resize());
        this.resizeObserver.observe(canvas);
        this.onVisibility = () => {
            this.cancelFrame();
            this.lastTime = 0;
            if (!document.hidden) this.requestFrame();
        };
        this.onMotion = () => this.requestFrame();
        document.addEventListener("visibilitychange", this.onVisibility);
        motionPreference.addEventListener("change", this.onMotion);
    }

    resize() {
        const bounds = this.canvas.getBoundingClientRect();
        this.width = bounds.width;
        this.height = bounds.height;
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        this.canvas.width = Math.round(this.width * ratio);
        this.canvas.height = Math.round(this.height * ratio);
        this.context.setTransform(ratio, 0, 0, ratio, 0, 0);
        this.requestFrame();
    }

    pattern(index) {
        const key = `${this.mode}:${index}`;
        if (this.cache.has(key)) return this.cache.get(key);
        const result = new Float32Array(this.count * 2);
        let seed = 1979 + index * 7919;
        const random = () => {
            seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
            return seed / 4294967296;
        };
        const lobes = 2 + index % 6;
        const bands = 3 + Math.floor(index / 3);
        for (let i = 0; i < this.count; i += 1) {
            let radius, angle;
            // Bounded rejection sampling collects grains near the field's nodes.
            for (let attempt = 0; attempt < 90; attempt += 1) {
                radius = Math.sqrt(random()) * 0.97;
                angle = random() * Math.PI * 2;
                const field = this.mode === "rings"
                    ? Math.sin(radius * Math.PI * (4 + index * 0.45))
                    : Math.cos(radius * Math.PI * bands) * Math.cos(angle * lobes)
                        + 0.65 * Math.cos(radius * Math.PI * (bands + 1))
                        * Math.sin(angle * (lobes + 2));
                if (Math.abs(field) < 0.075 + random() * 0.14) break;
            }
            result[i * 2] = radius * Math.cos(angle);
            result[i * 2 + 1] = radius * Math.sin(angle);
        }
        this.cache.set(key, result);
        return result;
    }

    setSignal(note, color) {
        const index = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"].indexOf(note);
        if (index < 0 || !this.available) return;
        const changed = this.note !== note;
        this.note = note;
        this.color = color;
        this.canvas.setAttribute("aria-label", `Patrón de la nota ${note.replace("#", " sostenido")}, color ${color}`);
        if (changed || !this.targets) {
            const first = !this.targets;
            this.targets = this.pattern(index);
            if (first) this.points.set(this.targets);
        }
        this.requestFrame();
    }

    setMode(mode) {
        this.mode = mode;
        this.stage.dataset.visualization = mode;
        this.targets = null;
        if (this.note) this.setSignal(this.note, this.color);
        this.cancelFrame();
        this.requestFrame();
    }

    setRunning(running) {
        if (this.running === running) return;
        this.running = running;
        this.requestFrame();
    }

    cancelFrame() {
        if (this.frame !== null) cancelAnimationFrame(this.frame);
        this.frame = null;
    }

    requestFrame() {
        if (!this.available || this.frame !== null || document.hidden || this.mode === "color") return;
        this.frame = requestAnimationFrame((time) => this.draw(time));
    }

    draw(time) {
        this.frame = null;
        const ctx = this.context;
        const dt = this.lastTime ? Math.min((time - this.lastTime) / 1000, 0.05) : 1 / 60;
        this.lastTime = time;
        const moving = !this.paused && !this.motionPreference.matches && this.running;
        if (moving) this.phase += dt;
        const radius = Math.max(0, Math.min(this.width, this.height) * 0.46);
        const cx = this.width / 2;
        const cy = this.height / 2;
        ctx.fillStyle = "#090D10";
        ctx.fillRect(0, 0, this.width, this.height);
        if (!this.targets) {
            ctx.strokeStyle = "#343B40";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(cx, cy, radius * 0.78, 0, Math.PI * 2);
            ctx.stroke();
            return;
        }

        const blend = moving ? 1 - Math.exp(-dt * 18) : 1;
        const breath = Math.sin(this.phase * 1.8);
        const drift = Math.cos(this.phase * 2.3);
        ctx.fillStyle = this.color;
        // Batch by brightness; no per-grain gradients, allocations or shadows.
        for (let group = 0; group < 3; group += 1) {
            ctx.globalAlpha = [0.28, 0.6, 0.95][group];
            const size = [1, 1.5, 1.9][group];
            for (let i = group; i < this.count; i += 3) {
                const p = i * 2;
                this.points[p] += (this.targets[p] - this.points[p]) * blend;
                this.points[p + 1] += (this.targets[p + 1] - this.points[p + 1]) * blend;
                const jitterX = moving ? breath * ((i % 13) / 13 - 0.5) * 1.7 : 0;
                const jitterY = moving ? drift * ((i % 17) / 17 - 0.5) * 1.7 : 0;
                ctx.fillRect(cx + this.points[p] * radius + jitterX,
                    cy + this.points[p + 1] * radius + jitterY, size, size);
            }
        }
        ctx.globalAlpha = 1;
        if (moving) this.requestFrame();
    }

    destroy() {
        this.cancelFrame();
        this.resizeObserver?.disconnect();
        document.removeEventListener("visibilitychange", this.onVisibility);
        this.motionPreference.removeEventListener("change", this.onMotion);
    }
}
