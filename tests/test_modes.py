"""Integracion de arranque web y adaptador Hue, sin dispositivos reales."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.main as api
from hardware.hue_client import HueController


class DeploymentModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(api, "TEMP_DIR", Path(self.temp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_web_ignores_hue_configuration_and_never_opens_hardware(self):
        with (
            patch.object(api, "HUE_ENABLED", False),
            patch.object(api, "HUE_LIGHT_IDS", ("old-local-light",)),
            patch.object(HueController, "__init__", side_effect=AssertionError("Hue initialized")),
            patch("requests.sessions.Session.request", side_effect=AssertionError("Network request")),
            patch.dict(sys.modules, {"aubio": None, "pyaudio": None, "audio.pitch_detector": None}),
            TestClient(api.app) as client,
        ):
            self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(client.get("/api/status").json()["running"], False)
            self.assertIs(client.get("/api/client-config").json()["hue_enabled"], False)
            self.assertEqual(client.get("/api/lights").json(), {"light_ids": []})
            self.assertIn("scriabin", client.get("/api/profiles").json())
            self.assertEqual(client.post("/api/listener/start").status_code, 409)
            self.assertEqual(client.post("/api/listener/stop").status_code, 200)
            self.assertEqual(client.post("/api/set_light", json={
                "light_id": "old-local-light", "r": 255, "g": 0, "b": 0,
            }).status_code, 409)
            self.assertEqual(client.post("/api/upload", files={
                "file": ("invalid.txt", b"text", "text/plain"),
            }).status_code, 415)

    def test_web_starts_with_no_lights(self):
        with patch.object(api, "HUE_ENABLED", False), patch.object(api, "HUE_LIGHT_IDS", ()):
            with TestClient(api.app) as client:
                self.assertEqual(client.get("/api/status").status_code, 200)

    def test_hue_requires_lights(self):
        with patch.object(api, "HUE_ENABLED", True), patch.object(api, "HUE_LIGHT_IDS", ()):
            with self.assertRaisesRegex(RuntimeError, "HUE_LIGHT_IDS"):
                with TestClient(api.app):
                    pass

    def test_hue_validates_credentials(self):
        with (
            patch.object(api, "HUE_ENABLED", True),
            patch.object(api, "HUE_LIGHT_IDS", ("local-light",)),
            patch.object(api, "HueController", side_effect=lambda: HueController("", "")),
        ):
            with self.assertRaisesRegex(ValueError, "BRIDGE_IP"):
                with TestClient(api.app):
                    pass

    def test_hue_still_sends_commands_without_native_audio_dependencies(self):
        with (
            patch.object(api, "HUE_ENABLED", True),
            patch.object(api, "HUE_LIGHT_IDS", ("local-light",)),
            patch.object(HueController, "__init__", return_value=None),
            patch.object(HueController, "set_color") as set_color,
            patch.dict(sys.modules, {"aubio": None, "pyaudio": None, "audio.pitch_detector": None}),
            TestClient(api.app) as client,
        ):
            self.assertIs(client.get("/api/client-config").json()["hue_enabled"], True)
            self.assertEqual(client.get("/api/lights").json()["light_ids"], ["local-light"])
            response = client.post("/api/set_light", json={
                "light_id": "local-light", "r": 10, "g": 20, "b": 30,
            })
            self.assertEqual(response.status_code, 200)
            set_color.assert_called_once_with("local-light", (10, 20, 30), 100)
            self.assertEqual(client.post("/api/set_light", json={
                "light_id": "unknown", "r": 10, "g": 20, "b": 30,
            }).status_code, 404)


if __name__ == "__main__":
    unittest.main()
