#!/usr/bin/python3
"""Rootless package staging/build; debian/rules uses the same installer."""
import argparse
from email.parser import Parser
import gzip
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from tallydesklet import __version__  # noqa: E402


def package_version():
    version = re.search(r"\(([^)]+)\)", (ROOT / "debian/changelog").read_text())[1]
    if version.rsplit("-", 1)[0] != __version__:
        raise SystemExit("debian/changelog version must match tallydesklet.__version__")
    return version


def stage(destination):
    destination.mkdir(parents=True, exist_ok=True)
    modules = destination / "usr/share/tallydesklet/tallydesklet"
    shutil.copytree(ROOT / "src/tallydesklet", modules, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    launcher = destination / "usr/bin/tallydesklet"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text('#!/usr/bin/python3\nimport sys\nsys.dont_write_bytecode = True\nsys.path.insert(0, "/usr/share/tallydesklet")\n'
                        'from tallydesklet.app import main\nraise SystemExit(main())\n')
    launcher.chmod(0o755)
    # Existing opt-in login entries and scripts can keep using the old command.
    legacy_launcher = destination / "usr/bin/mint-meter"
    shutil.copyfile(launcher, legacy_launcher)
    legacy_launcher.chmod(0o755)
    for source, target in (("data/tallydesklet.desktop", "usr/share/applications/tallydesklet.desktop"),
                           ("data/icons/tallydesklet.svg", "usr/share/icons/hicolor/scalable/apps/tallydesklet.svg"),
                           ("debian/copyright", "usr/share/doc/tallydesklet/copyright"),
                           ("README.md", "usr/share/doc/tallydesklet/README.md")):
        path = destination / target
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, path)
    shutil.copyfile(ROOT / "data/icons/tallydesklet.svg",
                    destination / "usr/share/icons/hicolor/scalable/apps/mint-meter.svg")
    (destination / "usr/share/doc/tallydesklet/changelog.Debian.gz").write_bytes(
        gzip.compress((ROOT / "debian/changelog").read_bytes(), mtime=0))
    # Test captures and resource reports contain machine-specific readings.
    # Ship only the public project documentation, never the whole docs tree.
    public_docs = destination / "usr/share/doc/tallydesklet/docs"
    public_docs.mkdir(parents=True, exist_ok=True)
    for name in ("BUILD_SPEC.md", "DESIGN.md", "TESTING.md", "RELEASING.md"):
        shutil.copyfile(ROOT / "docs" / name, public_docs / name)
    # These reviewed previews contain fixed example data, never live captures.
    for name in ("dark.png", "light.png", "settings.png"):
        source = ROOT / "docs/examples" / name
        if source.is_file():
            target = public_docs / "examples" / name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
    if (ROOT / "LICENSE").exists():
        shutil.copyfile(ROOT / "LICENSE", destination / "usr/share/doc/tallydesklet/LICENSE")
    man = destination / "usr/share/man/man1/tallydesklet.1.gz"
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_bytes(gzip.compress((ROOT / "data/tallydesklet.1").read_bytes(), mtime=0))
    (man.parent / "mint-meter.1.gz").write_bytes(
        gzip.compress(b".so man1/tallydesklet.1\n", mtime=0))


def build():
    version = package_version()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    artifact = dist / f"tallydesklet_{version}_all.deb"
    with tempfile.TemporaryDirectory(prefix="tallydesklet-build-") as temp:
        dest = Path(temp)
        stage(dest)
        control_dir = dest / "DEBIAN"
        control_dir.mkdir()
        paragraphs = (ROOT / "debian/control").read_text().split("\n\n")
        source, binary = (Parser().parsestr(v) for v in paragraphs[:2])
        deps = ", ".join(v.strip() for v in binary["Depends"].split(",") if "${" not in v)
        total = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
        control = (f"Package: tallydesklet\nVersion: {version}\nArchitecture: all\n"
                   f"Section: {source['Section']}\nPriority: optional\nMaintainer: {source['Maintainer']}\n"
                   f"Depends: {deps}\nInstalled-Size: {(total+1023)//1024}\nDescription: {binary['Description']}\n")
        for field in ("Conflicts", "Replaces", "Provides"):
            if binary[field]:
                control += f"{field}: {binary[field].replace('${binary:Version}', version)}\n"
        (control_dir / "control").write_text(control)
        hashes = []
        for path in sorted(dest.rglob("*")):
            if path.is_file() and control_dir not in path.parents:
                hashes.append(f"{hashlib.md5(path.read_bytes()).hexdigest()}  {path.relative_to(dest)}")
        (control_dir / "md5sums").write_text("\n".join(hashes) + "\n")
        epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "1791417600"))
        for path in dest.rglob("*"):
            os.utime(path, (epoch, epoch))
            if path.is_dir():
                path.chmod(0o755)
            elif path not in (dest / "usr/bin/tallydesklet", dest / "usr/bin/mint-meter"):
                path.chmod(0o644)
        dest.chmod(0o755)
        os.utime(dest, (epoch, epoch))
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(dest), str(artifact)], check=True,
                       env={**os.environ, "SOURCE_DATE_EPOCH": str(epoch)})
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (dist / "SHA256SUMS").write_text(f"{checksum}  {artifact.name}\n")
    subprocess.run(["dpkg-deb", "--info", str(artifact)], check=True)
    print(f"Built {artifact}\nSHA-256: {checksum}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--check-version", action="store_true")
    args = parser.parse_args()
    package_version()
    if args.stage:
        stage(args.stage)
    elif not args.check_version:
        build()
