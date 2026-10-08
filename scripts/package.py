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
from mint_meter import __version__  # noqa: E402


def package_version():
    version = re.search(r"\(([^)]+)\)", (ROOT / "debian/changelog").read_text())[1]
    if version.rsplit("-", 1)[0] != __version__:
        raise SystemExit("debian/changelog version must match mint_meter.__version__")
    return version


def stage(destination):
    destination.mkdir(parents=True, exist_ok=True)
    modules = destination / "usr/share/mint-meter/mint_meter"
    shutil.copytree(ROOT / "src/mint_meter", modules, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    launcher = destination / "usr/bin/mint-meter"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text('#!/usr/bin/python3\nimport sys\nsys.dont_write_bytecode = True\nsys.path.insert(0, "/usr/share/mint-meter")\n'
                        'from mint_meter.app import main\nraise SystemExit(main())\n')
    launcher.chmod(0o755)
    for source, target in (("data/mint-meter.desktop", "usr/share/applications/mint-meter.desktop"),
                           ("data/icons/mint-meter.svg", "usr/share/icons/hicolor/scalable/apps/mint-meter.svg"),
                           ("debian/copyright", "usr/share/doc/mint-meter/copyright"),
                           ("README.md", "usr/share/doc/mint-meter/README.md")):
        path = destination / target
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, path)
    (destination / "usr/share/doc/mint-meter/changelog.Debian.gz").write_bytes(
        gzip.compress((ROOT / "debian/changelog").read_bytes(), mtime=0))
    # Test captures and resource reports contain machine-specific readings.
    # Ship only the public project documentation, never the whole docs tree.
    public_docs = destination / "usr/share/doc/mint-meter/docs"
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
        shutil.copyfile(ROOT / "LICENSE", destination / "usr/share/doc/mint-meter/LICENSE")
    man = destination / "usr/share/man/man1/mint-meter.1.gz"
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_bytes(gzip.compress((ROOT / "data/mint-meter.1").read_bytes(), mtime=0))


def build():
    version = package_version()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    artifact = dist / f"mint-meter_{version}_all.deb"
    with tempfile.TemporaryDirectory(prefix="mint-meter-build-") as temp:
        dest = Path(temp)
        stage(dest)
        control_dir = dest / "DEBIAN"
        control_dir.mkdir()
        paragraphs = (ROOT / "debian/control").read_text().split("\n\n")
        source, binary = (Parser().parsestr(v) for v in paragraphs[:2])
        deps = ", ".join(v.strip() for v in binary["Depends"].split(",") if "${" not in v)
        total = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
        control = (f"Package: mint-meter\nVersion: {version}\nArchitecture: all\n"
                   f"Section: {source['Section']}\nPriority: optional\nMaintainer: {source['Maintainer']}\n"
                   f"Depends: {deps}\nInstalled-Size: {(total+1023)//1024}\nDescription: {binary['Description']}\n")
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
            elif path != dest / "usr/bin/mint-meter":
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
