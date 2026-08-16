"use strict";

const startButton = document.querySelector("#start-button");
const stopButton = document.querySelector("#stop-button");
const profileInputs = [...document.querySelectorAll('input[name="profile"]')];
const listenerStatus = document.querySelector("#listener-status");
const listenerDot = document.querySelector("#listener-dot");
const socketStatus = document.querySelector("#socket-status");
const socketDot = document.querySelector("#socket-dot");
const feedback = document.querySelector("#feedback");
const colorStage = document.querySelector("#main-content");
const colorHex = document.querySelector("#color-hex");
const noteDisplay = document.querySelector("#note-display");
const noteCaption = document.querySelector("#note-caption");
const activeProfileLabel = document.querySelector("#active-profile-label");
const scaleNotes = [...document.querySelectorAll(".scale-note")];
const themeMeta = document.querySelector('meta[name="theme-color"]');
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

let colorSocket = null;
let reconnectTimer = null;
let reconnectAttempt = 0;
let allowReconnect = true;
let controlsBusy = false;

const requiredElements = [
    startButton,
    stopButton,
    listenerStatus,
    listenerDot,
    socketStatus,
    socketDot,
    feedback,
    colorStage,
    colorHex,
    noteDisplay,
    noteCaption,
    activeProfileLabel,
];

if (requiredElements.some((element) => element === null)) {
    throw new Error("La interfaz no contiene todos los elementos requeridos.");
}

function setFeedback(message, tone = "neutral") {
    feedback.textContent = message;
    feedback.dataset.tone = tone;
}

function setBusy(isBusy) {
    controlsBusy = isBusy;
    profileInputs.forEach((input) => {
        input.disabled = isBusy;
    });
}

function capitalize(value) {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

function applyEngineStatus(status) {
    const running = Boolean(status.running);
    startButton.disabled = running || controlsBusy;
    stopButton.disabled = !running || controlsBusy;
    listenerStatus.textContent = running ? "Escuchando" : "En espera";
    listenerDot.dataset.state = running ? "listening" : "idle";

    if (typeof status.profile === "string") {
        const normalizedProfile = status.profile.toLowerCase();
        profileInputs.forEach((input) => {
            input.checked = input.value === normalizedProfile;
        });
        activeProfileLabel.textContent = capitalize(normalizedProfile);
    }

    if (status.last_error) {
        setFeedback(`La escucha se detuvo: ${status.last_error}`, "error");
    }
}

async function apiRequest(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        headers: {
            Accept: "application/json",
            ...(options.headers || {}),
        },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        const detail = typeof payload.detail === "string"
            ? payload.detail
            : "El servidor no pudo completar la acción.";
        throw new Error(detail);
    }
    return payload;
}

async function refreshStatus({ quiet = false } = {}) {
    try {
        const status = await apiRequest("/api/status");
        applyEngineStatus(status);
    } catch (error) {
        if (!quiet) {
            setFeedback(`No pudimos consultar el motor. ${error.message}`, "error");
        }
    }
}

async function startListening() {
    setBusy(true);
    startButton.disabled = true;
    stopButton.disabled = true;
    startButton.textContent = "Abriendo micrófono…";
    setFeedback("Preparando la entrada de audio…");

    try {
        const status = await apiRequest("/api/listener/start", { method: "POST" });
        applyEngineStatus(status);
        setFeedback("Escucha activa. Haz sonar una nota.");
        window.setTimeout(() => refreshStatus({ quiet: true }), 600);
    } catch (error) {
        setFeedback(`No pudimos iniciar la escucha. ${error.message}`, "error");
        await refreshStatus({ quiet: true });
    } finally {
        setBusy(false);
        startButton.textContent = "Iniciar escucha";
        await refreshStatus({ quiet: true });
    }
}

async function stopListening() {
    setBusy(true);
    startButton.disabled = true;
    stopButton.disabled = true;
    stopButton.textContent = "Deteniendo…";
    setFeedback("Cerrando el micrófono…");

    try {
        const status = await apiRequest("/api/listener/stop", { method: "POST" });
        applyEngineStatus(status);
        setFeedback("Micrófono detenido. El último color permanece visible.");
    } catch (error) {
        setFeedback(`No pudimos detener la escucha. ${error.message}`, "error");
        await refreshStatus({ quiet: true });
    } finally {
        setBusy(false);
        stopButton.textContent = "Detener";
        await refreshStatus({ quiet: true });
    }
}

async function changeProfile(input) {
    const previousProfile = activeProfileLabel.textContent.toLowerCase();
    const nextProfile = input.value;
    activeProfileLabel.textContent = capitalize(nextProfile);
    setBusy(true);
    setFeedback(`Cambiando al perfil ${capitalize(nextProfile)}…`);

    try {
        const response = await apiRequest(`/api/profile/${encodeURIComponent(nextProfile)}`, {
            method: "POST",
        });
        activeProfileLabel.textContent = capitalize(response.profile);
        setFeedback(`Perfil ${capitalize(response.profile)} activo.`);
    } catch (error) {
        profileInputs.forEach((profileInput) => {
            profileInput.checked = profileInput.value === previousProfile;
        });
        activeProfileLabel.textContent = capitalize(previousProfile);
        setFeedback(`No pudimos cambiar el perfil. ${error.message}`, "error");
    } finally {
        setBusy(false);
        await refreshStatus({ quiet: true });
    }
}

function isValidHexColor(value) {
    return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value);
}

function stageInkFor(hexColor) {
    const channels = [1, 3, 5].map((index) => Number.parseInt(hexColor.slice(index, index + 2), 16) / 255);
    const linear = channels.map((channel) => (
        channel <= 0.04045
            ? channel / 12.92
            : ((channel + 0.055) / 1.055) ** 2.4
    ));
    const luminance = (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2]);
    return luminance > 0.18 ? "#080b08" : "#fff9ef";
}

function showColorEvent(note, color) {
    if (typeof note !== "string" || !isValidHexColor(color)) {
        return;
    }

    const normalizedColor = color.toUpperCase();
    colorStage.style.setProperty("--detected-color", normalizedColor);
    colorStage.style.setProperty("--stage-ink", stageInkFor(normalizedColor));
    colorHex.textContent = normalizedColor;
    noteDisplay.textContent = note.replace("#", "♯");
    noteCaption.textContent = `Nota ${note.replace("#", " sostenido")}`;
    themeMeta?.setAttribute("content", normalizedColor);

    scaleNotes.forEach((scaleNote) => {
        if (scaleNote.dataset.note === note) {
            scaleNote.setAttribute("aria-current", "true");
        } else {
            scaleNote.removeAttribute("aria-current");
        }
    });

    if (!reducedMotion.matches) {
        noteDisplay.animate(
            [
                { opacity: 0.35, transform: "scale(0.96)" },
                { opacity: 1, transform: "scale(1)" },
            ],
            { duration: 180, easing: "cubic-bezier(0.16, 1, 0.3, 1)" },
        );
    }
}

function updateSocketState(label, state) {
    socketStatus.textContent = label;
    socketDot.dataset.state = state;
}

function scheduleReconnect() {
    if (!allowReconnect || reconnectTimer !== null) {
        return;
    }
    const delay = Math.min(500 * (2 ** reconnectAttempt), 5000);
    reconnectAttempt += 1;
    reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connectColorStream();
    }, delay);
}

function connectColorStream() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socketUrl = `${protocol}//${window.location.host}/ws/color_stream`;
    updateSocketState(reconnectAttempt > 0 ? "Reconectando" : "Conectando", "idle");
    colorSocket = new WebSocket(socketUrl);

    colorSocket.addEventListener("open", () => {
        reconnectAttempt = 0;
        updateSocketState("Conectado", "online");
    });

    colorSocket.addEventListener("message", (event) => {
        try {
            const message = JSON.parse(event.data);
            showColorEvent(message.nota, message.color);
        } catch (error) {
            setFeedback("Recibimos una señal de color que no pudimos interpretar.", "error");
        }
    });

    colorSocket.addEventListener("error", () => {
        updateSocketState("Sin conexión", "error");
    });

    colorSocket.addEventListener("close", () => {
        updateSocketState("Reconectando", "idle");
        scheduleReconnect();
    });
}

startButton.addEventListener("click", startListening);
stopButton.addEventListener("click", stopListening);
profileInputs.forEach((input) => {
    input.addEventListener("change", () => {
        if (input.checked) {
            changeProfile(input);
        }
    });
});

window.addEventListener("beforeunload", () => {
    allowReconnect = false;
    if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
    }
    colorSocket?.close();
});

refreshStatus();
connectColorStream();
window.setInterval(() => refreshStatus({ quiet: true }), 5000);
