"use strict";

const startButton = document.querySelector("#start-button");
const stopButton = document.querySelector("#stop-button");
const profileSelect = document.querySelector("#profile-select");
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
const audioFileInput = document.querySelector("#audio-file-input");
const trackPlayer = document.querySelector("#track-player");
const player = document.querySelector("#player");
const trackName = document.querySelector("#track-name");
const trackState = document.querySelector("#track-state");
const scaleNotes = [...document.querySelectorAll(".scale-note")];
const themeMeta = document.querySelector('meta[name="theme-color"]');
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

let sinestesiaProfiles = {};
let songTimeline = [];
let lightIds = [];
let activeTimelineIndex = -1;
let appliedTimelineSignature = "";
let pendingLightColor = null;
let sendingLightColor = false;
let profilesReady = false;
let colorSocket = null;
let reconnectTimer = null;
let reconnectAttempt = 0;
let allowReconnect = true;
let controlsBusy = false;
let engineIsRunning = false;

const requiredElements = [
    startButton,
    stopButton,
    profileSelect,
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
    audioFileInput,
    trackPlayer,
    player,
    trackName,
    trackState,
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
    profileSelect.disabled = isBusy || !profilesReady;
    audioFileInput.disabled = isBusy || !profilesReady;
}

function capitalize(value) {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

function isRgb(value) {
    return Array.isArray(value)
        && value.length === 3
        && value.every((channel) => Number.isInteger(channel) && channel >= 0 && channel <= 255);
}

function applyEngineStatus(status) {
    const running = Boolean(status.running);
    engineIsRunning = running;
    startButton.disabled = running || controlsBusy;
    stopButton.disabled = !running || controlsBusy;
    listenerStatus.textContent = running ? "Escuchando" : "En espera";
    listenerDot.dataset.state = running ? "listening" : "idle";

    if (typeof status.profile === "string" && sinestesiaProfiles[status.profile]) {
        profileSelect.value = status.profile;
        activeProfileLabel.textContent = capitalize(status.profile);
        activeProfileLabel.dataset.profile = status.profile;
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

async function loadApplicationData() {
    setBusy(true);
    setFeedback("Cargando perfiles históricos y luces…");
    try {
        const [profiles, lightsResponse] = await Promise.all([
            apiRequest("/api/profiles"),
            apiRequest("/api/lights"),
        ]);
        if (typeof profiles !== "object" || profiles === null || Object.keys(profiles).length === 0) {
            throw new Error("El servidor no devolvió perfiles sinestésicos.");
        }
        if (!Array.isArray(lightsResponse.light_ids) || lightsResponse.light_ids.length === 0) {
            throw new Error("No hay focos Hue configurados.");
        }

        sinestesiaProfiles = profiles;
        lightIds = lightsResponse.light_ids.filter((lightId) => typeof lightId === "string");
        [...profileSelect.options].forEach((option) => {
            option.disabled = !sinestesiaProfiles[option.value];
        });
        profilesReady = true;
        setFeedback(`${Object.keys(sinestesiaProfiles).length} perfiles listos para usar.`);
    } catch (error) {
        profilesReady = false;
        setFeedback(`No pudimos cargar la configuración. ${error.message}`, "error");
    } finally {
        setBusy(false);
    }
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
    player.pause();
    trackState.textContent = songTimeline.length > 0 ? "Pista en pausa" : "Sin pista";
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

async function changeProfile() {
    const previousProfile = activeProfileLabel.dataset.profile || "scriabin";
    const nextProfile = profileSelect.value;
    activeProfileLabel.textContent = capitalize(nextProfile);
    activeProfileLabel.dataset.profile = nextProfile;
    setBusy(true);
    setFeedback(`Aplicando el perfil ${capitalize(nextProfile)}…`);

    try {
        const response = await apiRequest(`/api/profile/${encodeURIComponent(nextProfile)}`, {
            method: "POST",
        });
        profileSelect.value = response.profile;
        activeProfileLabel.textContent = capitalize(response.profile);
        activeProfileLabel.dataset.profile = response.profile;
        appliedTimelineSignature = "";
        if (songTimeline.length > 0) {
            syncTrackColor(true);
            setFeedback(`Perfil ${capitalize(response.profile)} aplicado sin reprocesar la pista.`);
        } else {
            setFeedback(`Perfil ${capitalize(response.profile)} activo.`);
        }
    } catch (error) {
        profileSelect.value = previousProfile;
        activeProfileLabel.textContent = capitalize(previousProfile);
        activeProfileLabel.dataset.profile = previousProfile;
        setFeedback(`No pudimos cambiar el perfil. ${error.message}`, "error");
    } finally {
        setBusy(false);
        await refreshStatus({ quiet: true });
    }
}

function clearTrack() {
    player.pause();
    player.removeAttribute("src");
    player.load();
    songTimeline = [];
    activeTimelineIndex = -1;
    appliedTimelineSignature = "";
    pendingLightColor = null;
    trackName.textContent = "";
    trackState.textContent = "Sin pista";
    trackPlayer.hidden = true;
}

function isSupportedAudioFile(file) {
    const normalizedName = file.name.toLowerCase();
    return normalizedName.endsWith(".wav") || normalizedName.endsWith(".mp3");
}

function isTimelineEntry(entry) {
    return typeof entry === "object"
        && entry !== null
        && Number.isFinite(entry.time)
        && entry.time >= 0
        && typeof entry.note === "string";
}

async function uploadAudioTrack(file) {
    if (!isSupportedAudioFile(file)) {
        setFeedback("La pista debe ser un archivo WAV o MP3.", "error");
        return;
    }
    if (!profilesReady) {
        setFeedback("Los perfiles todavía no están disponibles. Recarga la página.", "error");
        return;
    }

    player.pause();
    setBusy(true);
    trackState.textContent = "Analizando notas…";
    setFeedback("Extrayendo una línea de tiempo reutilizable…");
    const formData = new FormData();
    formData.append("file", file);

    try {
        if (engineIsRunning) {
            const status = await apiRequest("/api/listener/stop", { method: "POST" });
            applyEngineStatus(status);
        }
        const response = await apiRequest("/api/upload", {
            method: "POST",
            body: formData,
        });
        if (!Array.isArray(response.timeline) || response.timeline.length === 0) {
            throw new Error("No detectamos notas suficientes en esta pista.");
        }
        if (!response.timeline.every(isTimelineEntry)) {
            throw new Error("La línea de tiempo recibida no tiene un formato válido.");
        }

        songTimeline = response.timeline;
        activeTimelineIndex = -1;
        appliedTimelineSignature = "";
        pendingLightColor = null;
        player.src = response.audio_url;
        player.load();
        trackName.textContent = file.name;
        trackState.textContent = `${songTimeline.length} cambios de nota`;
        trackPlayer.hidden = false;
        setFeedback("Timeline listo. Puedes cambiar de perfil sin analizar de nuevo.");
    } catch (error) {
        clearTrack();
        setFeedback(`No pudimos preparar la pista. ${error.message}`, "error");
    } finally {
        setBusy(false);
        audioFileInput.value = "";
        await refreshStatus({ quiet: true });
    }
}

function binarySearchTimeline(timeSeconds) {
    let low = 0;
    let high = songTimeline.length - 1;
    let match = -1;
    while (low <= high) {
        const middle = Math.floor((low + high) / 2);
        if (songTimeline[middle].time <= timeSeconds) {
            match = middle;
            low = middle + 1;
        } else {
            high = middle - 1;
        }
    }
    return match;
}

function findActiveTimelineIndex(timeSeconds) {
    if (
        activeTimelineIndex < 0
        || activeTimelineIndex >= songTimeline.length
        || songTimeline[activeTimelineIndex].time > timeSeconds
    ) {
        activeTimelineIndex = binarySearchTimeline(timeSeconds);
        return activeTimelineIndex;
    }

    while (
        activeTimelineIndex + 1 < songTimeline.length
        && songTimeline[activeTimelineIndex + 1].time <= timeSeconds
    ) {
        activeTimelineIndex += 1;
    }
    return activeTimelineIndex;
}

function rgbToHex(rgb) {
    return `#${rgb.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`.toUpperCase();
}

function queueLightColor(rgb) {
    pendingLightColor = [...rgb];
    if (!sendingLightColor) {
        void drainLightColorQueue();
    }
}

async function drainLightColorQueue() {
    sendingLightColor = true;
    while (pendingLightColor !== null) {
        const [r, g, b] = pendingLightColor;
        pendingLightColor = null;
        const results = await Promise.allSettled(
            lightIds.map((lightId) => apiRequest("/api/set_light", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    light_id: lightId,
                    r,
                    g,
                    b,
                    transition: 100,
                }),
            })),
        );
        const failures = results.filter((result) => result.status === "rejected");
        if (failures.length > 0) {
            setFeedback(
                `${failures.length} foco(s) no respondieron; la reproducción continúa.`,
                "error",
            );
        }
    }
    sendingLightColor = false;
}

function syncTrackColor(force = false) {
    if (songTimeline.length === 0 || (!force && player.paused)) {
        return;
    }
    const timelineIndex = findActiveTimelineIndex(player.currentTime);
    if (timelineIndex < 0) {
        return;
    }

    const activeNote = songTimeline[timelineIndex].note;
    const selectedProfile = profileSelect.value;
    const rgb = sinestesiaProfiles[selectedProfile]?.[activeNote];
    if (!isRgb(rgb)) {
        setFeedback(
            `El perfil ${capitalize(selectedProfile)} no contiene la nota ${activeNote}.`,
            "error",
        );
        return;
    }

    const signature = `${timelineIndex}:${selectedProfile}:${rgb.join(",")}`;
    if (!force && signature === appliedTimelineSignature) {
        return;
    }
    appliedTimelineSignature = signature;

    document.body.style.backgroundColor = `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
    showColorEvent(activeNote, rgbToHex(rgb));
    queueLightColor(rgb);
}

function isValidHexColor(value) {
    return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value);
}

function stageInkFor(hexColor) {
    const channels = [1, 3, 5].map(
        (index) => Number.parseInt(hexColor.slice(index, index + 2), 16) / 255,
    );
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
    document.body.style.backgroundColor = normalizedColor;
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
            if (songTimeline.length === 0 || engineIsRunning) {
                showColorEvent(message.nota, message.color);
            }
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
profileSelect.addEventListener("change", changeProfile);
audioFileInput.addEventListener("change", () => {
    const [file] = audioFileInput.files;
    if (file) {
        void uploadAudioTrack(file);
    }
});
player.addEventListener("play", () => {
    trackState.textContent = "Reproduciendo";
    syncTrackColor(true);
});
player.addEventListener("pause", () => {
    if (!player.ended && songTimeline.length > 0) {
        trackState.textContent = "Pista en pausa";
    }
});
player.addEventListener("ended", () => {
    trackState.textContent = "Pista terminada";
    activeTimelineIndex = -1;
    appliedTimelineSignature = "";
});
player.addEventListener("seeked", () => {
    activeTimelineIndex = -1;
    appliedTimelineSignature = "";
    syncTrackColor(true);
});
player.addEventListener("timeupdate", () => syncTrackColor());

window.addEventListener("beforeunload", () => {
    allowReconnect = false;
    if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
    }
    colorSocket?.close();
});

async function initialize() {
    connectColorStream();
    await loadApplicationData();
    await refreshStatus();
    window.setInterval(() => refreshStatus({ quiet: true }), 5000);
}

void initialize();
