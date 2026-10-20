"""Prueba HTTP con analisis WAV real dentro de la imagen, sin red externa."""

import importlib.util
import io
import json
import math
import os
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave


assert importlib.util.find_spec("pyaudio") is None
assert importlib.util.find_spec("aubio") is None
env = dict(os.environ, HUE_ENABLED="false", BRIDGE_IP="unreachable.invalid",
           HUE_APPLICATION_KEY="unused", HUE_LIGHT_IDS="unused")
server = subprocess.Popen([
    sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1",
    "--port", "8765",
], env=env)


def request(path, **kwargs):
    with urllib.request.urlopen(urllib.request.Request(
        "http://127.0.0.1:8765" + path, **kwargs,
    ), timeout=120) as response:
        return response.read()


try:
    deadline = time.monotonic() + 20
    while True:
        try:
            status = json.loads(request("/api/status"))
            break
        except (urllib.error.URLError, ConnectionError):
            if server.poll() is not None or time.monotonic() > deadline:
                raise
            time.sleep(0.1)
    assert status["running"] is False and status["last_error"] is None
    assert json.loads(request("/api/client-config"))["hue_enabled"] is False
    assert json.loads(request("/api/lights"))["light_ids"] == []
    assert b"Proyecto Sinestesia" in request("/")
    assert "scriabin" in json.loads(request("/api/profiles"))

    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        wav.writeframes(b"".join(struct.pack("<h", round(
            10000 * math.sin(2 * math.pi * 440 * i / 22050)
        )) for i in range(44100)))
    boundary = "sinestesia-test-boundary"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="tone.wav"\r\n'
        "Content-Type: audio/wav\r\n\r\n"
    ).encode() + audio.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    upload = json.loads(request("/api/upload", data=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }))
    assert any(cue["note"] == "A" for cue in upload["timeline"]), upload
    assert request(upload["audio_url"]) == audio.getvalue()
    print("PASS: web container starts without Hue/native audio; real WAV upload, note detection and playback URL.")
finally:
    server.terminate()
    server.wait(timeout=10)
