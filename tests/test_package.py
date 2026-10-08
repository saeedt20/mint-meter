"""Ensure private development artifacts never enter distributed packages."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class PackagePrivacyTests(unittest.TestCase):
    def test_only_public_documentation_is_shipped(self):
        spec = importlib.util.spec_from_file_location(
            "tallydesklet_packaging", Path(__file__).resolve().parents[1] / "scripts/package.py")
        packaging = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packaging)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            destination = Path(directory) / "package"
            public = ("BUILD_SPEC.md", "DESIGN.md", "TESTING.md", "RELEASING.md")
            files = ["src/tallydesklet/__init__.py", "data/tallydesklet.desktop",
                     "data/icons/tallydesklet.svg", "data/tallydesklet.1",
                     "debian/copyright", "debian/changelog", "README.md", "LICENSE"]
            files += [f"docs/{name}" for name in public]
            examples = ("dark.png", "light.png", "settings.png")
            files += [f"docs/examples/{name}" for name in examples]
            private = ["docs/screenshots/live.png", "docs/resource-check.json",
                       "docs/LOCAL_VERIFICATION.md", "docs/unknown-private-file.txt",
                       "docs/examples/unreviewed-private.png"]
            for name in files + private:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("PRIVATE_SENTINEL" if name in private else "public fixture")
            with patch.object(packaging, "ROOT", root):
                packaging.stage(destination)
            docs = destination / "usr/share/doc/tallydesklet/docs"
            self.assertEqual({p.name for p in docs.iterdir()}, set(public) | {"examples"})
            self.assertEqual({p.name for p in (docs / "examples").iterdir()}, set(examples))
            self.assertTrue((destination / "usr/share/doc/tallydesklet/LICENSE").is_file())
            for path in destination.rglob("*"):
                if path.is_file():
                    self.assertNotIn(b"PRIVATE_SENTINEL", path.read_bytes(), str(path))


if __name__ == "__main__":
    unittest.main()
