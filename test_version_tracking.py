import tempfile
import unittest
from pathlib import Path

from core.version_utils import get_installed_version, set_installed_version


class VersionTrackingTests(unittest.TestCase):
    def test_reads_from_config_and_updates_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            self.assertEqual(get_installed_version(base_dir), "1.0.9")

            set_installed_version("1.0.10", base_dir)
            self.assertEqual(get_installed_version(base_dir), "1.0.10")
            self.assertEqual((base_dir / "config" / "version.txt").read_text(encoding="utf-8").strip(), "1.0.10")


if __name__ == "__main__":
    unittest.main()
