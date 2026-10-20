"""Arranque del entrypoint configurado sin cargar el prototipo de imagenes."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


class VercelStartupTests(unittest.TestCase):
    def test_configured_entrypoint_starts_with_temporary_storage(self):
        script = '''
import importlib
from pathlib import Path
import sys
import tempfile
import tomllib
from unittest.mock import patch
from fastapi.testclient import TestClient

config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
module_name, app_name = config["tool"]["vercel"]["entrypoint"].split(":")
with patch.dict(sys.modules, {"colorthief": None, "pyaudio": None, "aubio": None}):
    api = importlib.import_module(module_name)
    assert api.TEMP_DIR.is_relative_to(Path(tempfile.gettempdir()))
    assert api.TEMP_DIR != api.PROJECT_ROOT / "temp"
    with TestClient(getattr(api, app_name)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/status").json()["running"] is False
        assert client.get("/api/client-config").json()["hue_enabled"] is False
        assert "scriabin" in client.get("/api/profiles").json()
        assert client.get("/static/index.html").status_code == 200
assert "image_analyzer" not in sys.modules
assert "hue_controller" not in sys.modules
'''
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            env=dict(os.environ, VERCEL="1", HUE_ENABLED="false"),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
