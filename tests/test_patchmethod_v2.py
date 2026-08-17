from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "bin" / "patchmethod_v2.py"
SMALI = """.class public Lexample/Test;
.super Ljava/lang/Object;

.method public isEnabled()Z
    .locals 1
    const/4 v0, 0x0
    return v0
.end method
"""


class PatchMethodV2Test(unittest.TestCase):
    def run_patch(self, method: str) -> tuple[subprocess.CompletedProcess[str], str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Test.smali"
            path.write_text(SMALI, encoding="utf-8")
            result = subprocess.run(
                ["python3", str(SCRIPT), str(path), method, "-return", "true"],
                check=False,
                text=True,
                capture_output=True,
            )
            return result, path.read_text(encoding="utf-8")

    def test_returns_success_and_patches_existing_method(self) -> None:
        result, content = self.run_patch("isEnabled")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("const/4 v0, 0x1", content)

    def test_returns_failure_when_method_is_missing(self) -> None:
        result, content = self.run_patch("doesNotExist")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(content, SMALI)


if __name__ == "__main__":
    unittest.main()
