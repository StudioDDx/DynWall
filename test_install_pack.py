"""Service installer contract: no GNOME extension pack dependency."""
from pathlib import Path
import ast
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent


class ServiceInstallerTests(unittest.TestCase):
    def test_installer_is_shell_valid(self):
        result = subprocess.run(["bash", "-n", str(ROOT / "install.sh")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cinematic_installer_embedded_python_is_valid(self):
        script = ROOT / "install-cinematic.sh"
        result = subprocess.run(["bash", "-n", str(script)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        source = script.read_text()
        self.assertEqual(source.count("<<'PY'"), 1)
        body = source.split("<<'PY'\\n", 1)[1].split("\\nPY\\n", 1)[0]
        ast.parse(body)

    def test_service_uses_native_slideshow(self):
        service = (ROOT / "systemd/dynwall.service").read_text()
        self.assertIn("ExecStart=%h/.local/bin/dynwall --play", service)
        installer = (ROOT / "install.sh").read_text()
        self.assertNotIn("gnome-extensions pack", installer)
        self.assertNotIn("gnome-extensions install", installer)
        self.assertIn("gnome-extensions disable dynwall@rucaradio", installer)


if __name__ == "__main__":
    unittest.main()
